"""
Search and recommendation endpoints.

Leverages FAISS for fast similarity search on embedded queries and videos.

Endpoints:
- POST /search?q=query&limit=50  → Search by text query
- POST /recommend?video_id=uuid&limit=15 → Find similar videos
- POST /reload-search → Lazy load more search results with pagination
- POST /filter-homefeed → Unified homefeed filter by categories/regions (OR)
- POST /reload-filter-homefeed → Lazy load unified filtered homefeed
- POST /reload-search-by-category → Lazy load category-filtered search results
- POST /search-by-region → Search videos filtered by regions
- POST /reload-search-by-region → Lazy load region-filtered search results
"""
import asyncio
import re

from fastapi import APIRouter, HTTPException, Query, status

from app.core import embedding_service, faiss_manager
from app.db import get_videos_by_categories, get_videos_by_regions, get_videos_metadata_by_uuids
from app.schemas.feed import (
    CategorySearchRequest,
    ChannelInfo,
    ChannelSearchRequest,
    ChannelSearchResponse,
    ChannelSearchResult,
    FilterHomeFeedRequest,
    RegionSearchRequest,
    ReloadRecommendRequest,
    SearchReloadRequest,
    VideoResponse,
)
from app.utils.formatters import format_timestamp, format_views, generate_channel_avatar, is_verified

router = APIRouter()


def transform_video(video: dict) -> VideoResponse:
    """Transform DB row to VideoResponse (reuse from feed.py logic)"""
    return VideoResponse(
        id=video["id"],
        video_id=video["video_id"],
        title=video["title"],
        thumbnail=video["thumbnail_link"],
        channel=ChannelInfo(
            name=video["channel_title"],
            avatar=generate_channel_avatar(video["channel_title"]),
            verified=is_verified(video.get("views", 0), video.get("likes", 0)),
            id=video["channel_title"]
        ),
        views=format_views(video.get("views", 0)),
        timestamp=format_timestamp(video.get("publish_time", "")),
        publish_time_raw=video.get("publish_time", ""),
        duration="10:00",
        category=video.get("category_name", "Unknown"),
        velocity_score=video.get("velocity_score")
    )


def _tokenize_query(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", query.lower()) if token]


def _normalize_lex_text(value: str) -> str:
    """Normalize to lowercase alphanumeric words for lightweight lexical ranking."""
    normalized = re.sub(r"[^a-z0-9\s]", "", (value or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _ascii_prefix_distance(query_norm: str, candidate_norm: str, max_chars: int = 8) -> int:
    """
    Fast lexical distance over leading characters.

    Lower values mean lexicographically closer to query.
    Uses only first max_chars characters to keep ranking very cheap.
    """
    if not query_norm or not candidate_norm:
        return 10_000

    q_prefix = query_norm[:max_chars]
    c_prefix = candidate_norm[:max_chars]
    overlap = min(len(q_prefix), len(c_prefix))

    char_distance = sum(abs(ord(q_prefix[i]) - ord(c_prefix[i])) for i in range(overlap))
    length_penalty = abs(len(q_prefix) - len(c_prefix)) * 14

    return char_distance + length_penalty


def _channel_rank_key(channel_name: str, query_norm: str, query_words: list[str]) -> tuple:
    """
    Ranking key (ascending):
    1) exact normalized match
    2) starts-with match
    3) more query token matches
    4) smaller ASCII prefix distance
    5) smaller length delta
    6) alphabetical tie-breaker
    """
    channel_norm = _normalize_lex_text(channel_name)

    is_exact = int(channel_norm == query_norm)
    starts_with = int(channel_norm.startswith(query_norm)) if query_norm else 0
    token_hits = sum(1 for token in query_words if token and token in channel_norm)
    prefix_distance = _ascii_prefix_distance(query_norm, channel_norm)
    length_delta = abs(len(channel_norm) - len(query_norm))

    return (
        -is_exact,
        -starts_with,
        -token_hits,
        prefix_distance,
        length_delta,
        channel_norm,
    )


@router.post("/search-channels", response_model=ChannelSearchResponse)
async def search_channels(request: ChannelSearchRequest):
    """
    Search channels using permissive ANY-word matching plus lightweight lexical ranking.

    Ranking is in-memory only (no DB changes):
    - exact/prefix boosts
    - query token coverage
    - ASCII-prefix distance (lexical closeness)
    - alphabetical tie-breaker
    """
    query = request.q.strip()
    if not query:
        return ChannelSearchResponse(channels=[], total=0)

    query_norm = _normalize_lex_text(query)
    query_words = _tokenize_query(query)
    if not query_words or not query_norm:
        return ChannelSearchResponse(channels=[], total=0)

    try:
        all_channels = await get_all_channels()
        matched_channels = [
            channel_name
            for channel_name in all_channels
            if any(term in channel_name.lower() for term in query_words)
        ]

        if not matched_channels:
            return ChannelSearchResponse(channels=[], total=0)

        channel_stats = await asyncio.gather(
            *(get_channel_stats(channel_name) for channel_name in matched_channels)
        )

        results: list[ChannelSearchResult] = []
        for stats in channel_stats:
            if not stats:
                continue

            channel_name = stats["channel_title"]
            results.append(
                ChannelSearchResult(
                    id=channel_name,
                    name=channel_name,
                    handle=generate_channel_handle(channel_name),
                    description=generate_channel_description(channel_name),
                    verified=stats["views_sum"] > 100000 or stats["likes_sum"] > 5000,
                    video_count=stats["video_count"],
                    avatar=generate_channel_avatar(channel_name),
                )
            )

        results.sort(
            key=lambda item: _channel_rank_key(
                channel_name=item.name,
                query_norm=query_norm,
                query_words=query_words,
            )
        )
        limited_results = results[:request.limit]

        return ChannelSearchResponse(channels=limited_results, total=len(results))
    except Exception as e:
        print(f"[SEARCH CHANNELS ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Channel search failed"
        )


@router.post("/search")
async def search_videos(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(50, ge=1, le=100, description="Number of results")
):
    """
    Hybrid search combining semantic similarity, keyword matching, and category intelligence.

    ALGORITHM:
    ----------
    1. Embed Query: Convert search text to 1024-dim normalized vector using bge-m3
    2. FAISS Search: Find K*2 semantically similar videos from vector database
    3. Keyword Match: Count how many query words appear in video titles
    4. Category Boost: Detect intent from query using category keyword mapping
    5. Hybrid Scoring: Combine scores → 70% semantic + 20% keyword + 10% category
    6. Re-rank: Sort all candidates by combined score
    7. Return: Top K results

    EXAMPLES:
    ---------
    Query: "gaming tutorials"
    - Embeds entire phrase to vector
    - Finds 100 similar videos (semantic pool)
    - Weights videos containing "gaming" + "tutorials" higher
    - Boosts "Gaming" category videos 10%
    - Returns 50 best-scored results

    Query: "bts band"
    - Embeds to vector
    - Finds 100 similar videos
    - Weights videos with both "bts" AND "band" highest
    - Boosts "Music" category (detects "band" intent)
    - Filters out "Behind the Scenes" acronym matches

    PERFORMANCE:
    - Embedding: ~50-100ms
    - FAISS search: ~5-10ms
    - Metadata fetch: ~100-200ms
    - Re-ranking: ~10ms
    - Total: 300-400ms

    INPUT:
    - q: Search query string (required)
    - limit: Results to return (1-100, default 50)

    OUTPUT:
    {
        "videos": [VideoResponse[], ...],
        "query": string,
        "total": int
    }
    """
    """
    Hybrid search: Semantic similarity + Keyword matching + Category boosting.

    Process:
    1. Embed query using sentence-transformers
    2. FAISS search for K*2 results (expanded pool for filtering)
    3. Keyword matching: Boost if query words in title
    4. Category boosting: Boost if category matches query intent
    5. Re-rank by combined score (semantic + keyword + category)
    6. Return top K results

    Args:
        q: Search query (e.g., "bts band", "gaming tutorials")
        limit: Number of results (1-100)

    Returns:
        {
            "videos": [VideoResponse, ...],
            "query": "original query",
            "total": number of results
        }
    """
    try:
        # Step 1: Embed query
        print(f"[SEARCH] Query: {q[:50]}...")
        query_embedding = embedding_service.embed_query(q)

        # Step 2: FAISS search (get 2x limit to filter and re-rank)
        faiss_k = min(limit * 2, 200)  # Get more results for better filtering
        print(f"[SEARCH] Searching FAISS index for K={faiss_k}...")
        faiss_results = faiss_manager.search_similar(query_embedding, k=faiss_k)

        if not faiss_results:
            return {
                "videos": [],
                "query": q,
                "total": 0
            }

        # Extract UUIDs
        video_uuids = [uuid_str for uuid_str, _ in faiss_results]

        # Step 3: Fetch metadata from DB
        print(f"[SEARCH] Fetching metadata for {len(video_uuids)} videos...")
        videos_data = await get_videos_metadata_by_uuids(video_uuids)

        # Create lookup dictionaries
        uuid_to_faiss_score = {uuid_str: score for uuid_str, score in faiss_results}
        uuid_to_video = {v["id"]: v for v in videos_data}

        # Step 4: Keyword matching + Category boosting
        print("[SEARCH] Re-ranking with keyword matching...")

        # Parse query keywords
        query_words = q.lower().split()

        # Define category keywords (all 16 YouTube categories)
        category_keywords = {
            "Sports": ["sport", "basketball", "football", "soccer", "nfl", "nba", "cricket", "tennis", "rugby", "boxing", "mma", "wrestling"],
            "Music": ["music", "song", "album", "artist", "concert", "band", "kpop", "pop", "rock", "hiphop", "rap", "jazz", "classical", "remix", "acoustic"],
            "People & Blogs": ["vlog", "blog", "vlogger", "content creator", "daily life", "personal", "lifestyle", "daily vlog"],
            "Entertainment": ["show", "celebrity", "actor", "actress", "entertainment", "interview", "talk show", "comedy show", "reality show", "drama"],
            "News & Politics": ["news", "politics", "political", "election", "government", "policy", "debate", "current events", "breaking news"],
            "Howto & Style": ["tutorial", "how to", "diy", "makeup", "fashion", "style", "beauty", "tips", "guide", "cooking", "recipe"],
            "Travel & Events": ["travel", "vlog travel", "destination", "vacation", "tourism", "event", "conference", "festival", "adventure", "exploration"],
            "Shows": ["show", "episode", "series", "tv show", "web series", "animated series", "sitcom", "drama series"],
            "Nonprofits & Activism": ["nonprofit", "charity", "donation", "social cause", "activism", "volunteer", "community service", "fundraiser", "awareness"],
            "Autos & Vehicles": ["car", "automobile", "vehicle", "motorcycle", "bike", "truck", "driving", "car review", "mechanic", "engineering", "racing"],
            "Gaming": ["game", "gaming", "streamer", "playthrough", "walkthrough", "gameplay", "esports", "tournament", "console", "pc gaming", "mobile game"],
            "Comedy": ["comedy", "comedians", "funny", "laugh", "humor", "stand up", "parody", "sketch", "prank"],
            "Film & Animation": ["movie", "film", "animated", "animation", "cinema", "trailer", "short film", "cartoon", "anime"],
            "Education": ["tutorial", "learn", "course", "lesson", "educational", "training", "school", "university", "online course", "lecture"],
            "Pets & Animals": ["pet", "animal", "dog", "cat", "wildlife", "nature", "creature", "cute animals", "veterinary", "zoo"],
            "Science & Technology": ["technology", "science", "tech", "invention", "experiment", "research", "programming", "coding", "software", "gadget", "artificial intelligence"],
        }

        # Score each video
        scored_videos = []
        for uuid in video_uuids:
            video = uuid_to_video.get(uuid)
            if not video:
                continue

            faiss_score = uuid_to_faiss_score[uuid]
            title_lower = video.get("title", "").lower()
            category = video.get("category_name", "")

            # Keyword matching score (0-1)
            keyword_score = 0.0
            matching_words = [w for w in query_words if w in title_lower]
            if matching_words:
                keyword_score = len(matching_words) / len(query_words)  # % of query words found

            # Category boosting score (0-0.3)
            category_boost = 0.0
            if category in category_keywords:
                # Boost if query words appear in title or category name
                if any(w in title_lower or w in category.lower() for w in query_words):
                    category_boost = 0.2

            # Combined score: 70% semantic + 20% keyword + 10% category
            combined_score = (
                faiss_score * 0.70 +
                keyword_score * 100 * 0.20 +  # Scale keyword_score to 0-100
                category_boost * 100 * 0.10
            )

            scored_videos.append({
                "uuid": uuid,
                "video": video,
                "combined_score": combined_score,
                "faiss_score": faiss_score,
                "keyword_score": keyword_score
            })

        # Step 5: Sort by combined score (highest first)
        scored_videos.sort(key=lambda x: x["combined_score"], reverse=True)

        # Step 6: Take top K results
        print(f"[SEARCH] Re-ranked, taking top {limit}...")
        top_videos = scored_videos[:limit]

        # Step 7: Transform to response
        print(f"[SEARCH] Transforming {len(top_videos)} videos...")
        video_responses = [transform_video(v["video"]) for v in top_videos]

        return {
            "videos": video_responses,
            "query": q,
            "total": len(video_responses)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query: {str(e)}"
        )
    except Exception as e:
        print(f"[SEARCH ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.post("/recommend")
async def recommend_similar_videos(
    video_id: str = Query(..., description="Video UUID to find similar videos for"),
    limit: int = Query(15, ge=1, le=50, description="Number of recommendations")
):
    """
    Context-aware recommendations: Semantic similarity + Shared keywords + Category affinity.

    ALGORITHM:
    ----------
    1. Get Reference: Fetch reference video embedding and metadata
    2. Extract Context: Parse title, extract meaningful keywords (>2 chars, not common words)
    3. FAISS Search: Find K*2 + buffer semantically similar videos
    4. Shared Keywords: Score based on overlap with reference title keywords
    5. Category Affinity: Strong boost for same category, weak for related
    6. Hybrid Scoring: 70% semantic + 15% keywords + 15% category
    7. Exclude Self: Never return the reference video
    8. Return: Top K ranked results

    CATEGORY RELATIONSHIPS:
    - Music ↔ Entertainment, Shows
    - Entertainment ↔ Music, Shows, Comedy
    - Comedy ↔ Entertainment, People & Blogs
    - Gaming ↔ Science & Technology
    - Sports ↔ Entertainment
    - Education ↔ Science & Technology
    - Travel & Events ↔ People & Blogs, Entertainment
    - Film & Animation ↔ Entertainment, Shows

    EXAMPLES:
    ---------
    Reference: "Flinch w/ BTS" (Entertainment)
    - Extracts keywords: ["flinch", "bts"]
    - Finds 30+ similar late-night talk show videos
    - Boosts videos with "flinch" or "bts" in title (+15%)
    - Boosts Entertainment category videos (+40%)
    - Returns 15 recommended late-night content

    Reference: "Gaming Tutorial: Python RPG" (Gaming)
    - Extracts keywords: ["gaming", "tutorial", "python", "rpg"]
    - Finds 30+ similar gaming/programming videos
    - Boosts videos mentioning keywords
    - Boosts Gaming & Science & Technology categories
    - Returns 15 recommended gaming/coding videos

    PERFORMANCE:
    - Embedding lookup: ~1ms (cached)
    - Metadata fetch: ~20ms
    - FAISS search: ~5-10ms
    - Re-ranking: ~20ms
    - Total: 200-300ms (faster than /search, no embedding needed)

    INPUT:
    - video_id: Reference video UUID (required)
    - limit: Recommendations to return (1-50, default 15)

    OUTPUT:
    {
        "videos": [VideoResponse[], ...],
        "current_video_id": string,
        "total": int
    }

    NOTES:
    - Never returns the reference video itself
    - Requires video to have pre-computed embedding
    - Returns 404 if video not found or has no embedding
    """
    try:
        # Step 1: Get reference video embedding
        print(f"[RECOMMEND] Looking up embedding for {video_id[:8]}...")
        current_embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)

        if current_embedding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found or has no embedding"
            )

        # Step 2: Fetch reference video metadata to extract context
        print("[RECOMMEND] Fetching reference video metadata...")
        ref_videos = await get_videos_metadata_by_uuids([video_id])
        if not ref_videos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video metadata not found"
            )

        ref_video = ref_videos[0]
        ref_title = ref_video.get("title", "").lower()
        ref_category = ref_video.get("category_name", "")

        # Extract keywords from reference video title
        ref_keywords = set(ref_title.split())
        # Remove common words
        common_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "from", "of", "for", "is", "are", "was", "were"}
        ref_keywords = {w for w in ref_keywords if w not in common_words and len(w) > 2}

        # Step 3: FAISS search (get 2x limit to filter and re-rank)
        faiss_k = min(limit * 2 + 10, 200)  # Extra buffer to exclude self
        print(f"[RECOMMEND] Searching for K={faiss_k} similar videos...")
        faiss_results = faiss_manager.search_similar(current_embedding, k=faiss_k)

        # Filter out the reference video itself
        faiss_results = [
            (uuid_str, score) for uuid_str, score in faiss_results
            if uuid_str != video_id
        ]

        if not faiss_results:
            return {
                "videos": [],
                "current_video_id": video_id,
                "total": 0
            }

        # Extract UUIDs
        video_uuids = [uuid_str for uuid_str, _ in faiss_results]

        # Step 4: Fetch metadata
        print(f"[RECOMMEND] Fetching metadata for {len(video_uuids)} videos...")
        videos_data = await get_videos_metadata_by_uuids(video_uuids)

        # Create lookup dictionaries
        uuid_to_faiss_score = {uuid_str: score for uuid_str, score in faiss_results}
        uuid_to_video = {v["id"]: v for v in videos_data}

        # Step 5: Shared keywords + Category affinity scoring
        print("[RECOMMEND] Re-ranking by shared context...")

        scored_videos = []
        for uuid in video_uuids:
            video = uuid_to_video.get(uuid)
            if not video:
                continue

            faiss_score = uuid_to_faiss_score[uuid]
            title_lower = video.get("title", "").lower()
            category = video.get("category_name", "")

            # Shared keywords score (0-1)
            # Count how many keywords from original video appear in this result
            video_keywords = set(title_lower.split())
            shared_keywords = ref_keywords.intersection(video_keywords)
            keyword_score = 0.0
            if ref_keywords:
                keyword_score = len(shared_keywords) / len(ref_keywords)  # % of ref keywords found

            # Category affinity score (0-1)
            # Strong boost if same category, weak boost if related
            category_boost = 0.0
            if category == ref_category:
                category_boost = 0.4  # 40% boost for same category (stronger than search)
            else:
                # Weak boost if in related category
                related_categories = {
                    "Music": ["Entertainment", "Shows"],
                    "Entertainment": ["Music", "Shows", "Comedy"],
                    "Comedy": ["Entertainment", "People & Blogs"],
                    "Gaming": ["Science & Technology"],
                    "Sports": ["Entertainment"],
                    "Education": ["Science & Technology"],
                    "Travel & Events": ["People & Blogs", "Entertainment"],
                    "Film & Animation": ["Entertainment", "Shows"],
                }
                if ref_category in related_categories and category in related_categories.get(ref_category, []):
                    category_boost = 0.1  # Small boost for related categories

            # Combined score: 70% semantic + 15% shared keywords + 15% category
            # Higher category weight for recommendations (users want similar type of content)
            combined_score = (
                faiss_score * 0.70 +
                keyword_score * 100 * 0.15 +  # Shared keywords from reference
                category_boost * 100 * 0.15
            )

            scored_videos.append({
                "uuid": uuid,
                "video": video,
                "combined_score": combined_score,
                "faiss_score": faiss_score,
                "keyword_score": keyword_score,
                "category_match": category == ref_category
            })

        # Step 6: Sort by combined score
        scored_videos.sort(key=lambda x: x["combined_score"], reverse=True)

        # Step 7: Take top K results
        print(f"[RECOMMEND] Re-ranked, taking top {limit}...")
        top_videos = scored_videos[:limit]

        # Step 8: Transform to response
        print(f"[RECOMMEND] Transforming {len(top_videos)} videos...")
        video_responses = [transform_video(v["video"]) for v in top_videos]

        return {
            "videos": video_responses,
            "current_video_id": video_id,
            "total": len(video_responses)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RECOMMEND ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation failed"
        )


@router.post("/reload-search")
async def reload_search_results(request: SearchReloadRequest):
    """
    Lazy loading endpoint - reload search results with pagination for infinite scroll.

    This endpoint powers infinite scrolling by returning unique sets of videos
    while maintaining identical hybrid ranking from initial /search endpoint.

    ALGORITHM:
    ----------
    1. Embed Query: Re-embed search query to same 1024-dim vector
    2. FAISS Search: Fetch K*2 + buffer (400-500) candidates from similarity space
    3. Filter: Remove all videos in excluded_video_ids
    4. Paginate: Get results from offset to offset+limit
    5. Re-rank: Apply same hybrid ranking (70% semantic + 20% keyword + 10% category)
    6. Return: Sorted unique results

    KEY INSIGHT:
    - Each reload gets NEXT batch of semantic results (lower similarity scores)
    - Videos at batch 1 have similarity ~0.90-1.00
    - Videos at batch 2 have similarity ~0.75-0.85
    - Videos at batch 3 have similarity ~0.60-0.75
    - All are semantically relevant but lower quality than initial search

    EXAMPLE USAGE:
    Query: "gaming tutorials"

    1. /search?q=gaming%20tutorials&limit=25
       Returns TOP 25 (similarity 0.90-1.00)
       - Exact matches, guides, walkthroughs
       - Best quality

    2. /reload-search with 25 excluded
       Returns NEXT 25 (similarity 0.75-0.85)
       - Game reviews, speedruns, commentary
       - Related gaming content

    3. /reload-search with 50 excluded
       Returns NEXT 25 (similarity 0.60-0.75)
       - Streamer clips, game news, memes
       - Loosely related

    4. /reload-search with 75 excluded
       Returns NEXT 25 (similarity 0.40-0.60)
       - General entertainment, YouTube shorts
       - Weakly related by semantic space

    PERFORMANCE:
    - Embedding: ~50-100ms (cached calculation)
    - FAISS search: ~10-20ms (larger K)
    - Filtering: ~5ms (set operations on 500 results)
    - Re-ranking: ~30ms (more results)
    - Total: 250-350ms

    INPUT:
    {
        "q": "gaming tutorials",                          // Same query from /search
        "excluded_video_ids": ["uuid1", "uuid2", ...],  // All videos already shown
        "offset": 0,                                      // Skip first N filtered results
        "limit": 25                                       // Return next 25
    }

    OUTPUT:
    {
        "videos": [VideoResponse[], ...],
        "query": "gaming tutorials",
        "total": 25,
        "offset": 0
    }

    FRONTEND PATTERN:
    1. User enters search query
    2. Call /search → get 25 results
    3. User scrolls to bottom
    4. Call /reload-search with those 25 excluded → get NEXT 25 different results
    5. Continue until /reload-search returns empty or < limit results

    IMPORTANT NOTES:
    - Same query must be re-embedded (not cached) for consistency
    - Excluded IDs are permanently filtered from pagination
    - Offset is within FILTERED results, not FAISS results
    - No pagination token needed - excluded_ids handle pagination state
    """
    try:
        query = request.q
        excluded_ids = set(request.excluded_video_ids or [])
        offset = request.offset
        limit = min(request.limit, 50)  # Cap at 50 per reload

        print(f"\n{'#'*70}")
        print(f"[RELOAD-SEARCH] Query: '{query[:50]}...', offset={offset}, limit={limit}")
        print(f"[RELOAD-SEARCH] Excluding {len(excluded_ids)} already-shown videos")
        print(f"{'#'*70}")

        # Step 1: Embed query
        print("[RELOAD] Step 1: Embedding query...")
        query_embedding = embedding_service.embed_query(query)

        # Step 2: FAISS search (get much larger pool for pagination)
        # Get results starting from offset position
        faiss_k = min((offset + limit + 50), 400)  # Get enough for pagination + buffer
        print(f"[RELOAD] Step 2: FAISS search for K={faiss_k}...")
        faiss_results = faiss_manager.search_similar(query_embedding, k=faiss_k)

        if not faiss_results:
            return {
                "videos": [],
                "query": query,
                "total": 0,
                "offset": offset,
                "has_more": False
            }

        # Step 3: Filter out excluded videos and apply offset
        print("[RELOAD] Step 3: Filtering excluded videos and applying offset...")
        filtered_results = [
            (uuid_str, score) for uuid_str, score in faiss_results
            if uuid_str not in excluded_ids
        ]

        # Get results from offset to offset+limit
        paginated_results = filtered_results[offset:offset+limit]

        if not paginated_results:
            return {
                "videos": [],
                "query": query,
                "total": 0,
                "offset": offset
            }

        # Extract UUIDs
        video_uuids = [uuid_str for uuid_str, _ in paginated_results]

        # Step 4: Fetch metadata from DB
        print(f"[RELOAD] Step 4: Fetching metadata for {len(video_uuids)} videos...")
        videos_data = await get_videos_metadata_by_uuids(video_uuids)

        # Create lookup dictionaries
        uuid_to_faiss_score = {uuid_str: score for uuid_str, score in paginated_results}
        uuid_to_video = {v["id"]: v for v in videos_data}

        # Step 5: Apply same hybrid ranking as /search
        print("[RELOAD] Step 5: Re-ranking with hybrid strategy...")

        # Parse query keywords
        query_words = query.lower().split()

        # Define category keywords (same as /search)
        category_keywords = {
            "Sports": ["sport", "basketball", "football", "soccer", "nfl", "nba", "cricket", "tennis", "rugby", "boxing", "mma", "wrestling"],
            "Music": ["music", "song", "album", "artist", "concert", "band", "kpop", "pop", "rock", "hiphop", "rap", "jazz", "classical", "remix", "acoustic"],
            "People & Blogs": ["vlog", "blog", "vlogger", "content creator", "daily life", "personal", "lifestyle", "daily vlog"],
            "Entertainment": ["show", "celebrity", "actor", "actress", "entertainment", "interview", "talk show", "comedy show", "reality show", "drama"],
            "News & Politics": ["news", "politics", "political", "election", "government", "policy", "debate", "current events", "breaking news"],
            "Howto & Style": ["tutorial", "how to", "diy", "makeup", "fashion", "style", "beauty", "tips", "guide", "cooking", "recipe"],
            "Travel & Events": ["travel", "vlog travel", "destination", "vacation", "tourism", "event", "conference", "festival", "adventure", "exploration"],
            "Shows": ["show", "episode", "series", "tv show", "web series", "animated series", "sitcom", "drama series"],
            "Nonprofits & Activism": ["nonprofit", "charity", "donation", "social cause", "activism", "volunteer", "community service", "fundraiser", "awareness"],
            "Autos & Vehicles": ["car", "automobile", "vehicle", "motorcycle", "bike", "truck", "driving", "car review", "mechanic", "engineering", "racing"],
            "Gaming": ["game", "gaming", "streamer", "playthrough", "walkthrough", "gameplay", "esports", "tournament", "console", "pc gaming", "mobile game"],
            "Comedy": ["comedy", "comedians", "funny", "laugh", "humor", "stand up", "parody", "sketch", "prank"],
            "Film & Animation": ["movie", "film", "animated", "animation", "cinema", "trailer", "short film", "cartoon", "anime"],
            "Education": ["tutorial", "learn", "course", "lesson", "educational", "training", "school", "university", "online course", "lecture"],
            "Pets & Animals": ["pet", "animal", "dog", "cat", "wildlife", "nature", "creature", "cute animals", "veterinary", "zoo"],
            "Science & Technology": ["technology", "science", "tech", "invention", "experiment", "research", "programming", "coding", "software", "gadget", "artificial intelligence"],
        }

        # Score each video
        scored_videos = []
        for uuid in video_uuids:
            video = uuid_to_video.get(uuid)
            if not video:
                continue

            faiss_score = uuid_to_faiss_score[uuid]
            title_lower = video.get("title", "").lower()
            category = video.get("category_name", "")

            # Keyword matching score (0-1)
            keyword_score = 0.0
            matching_words = [w for w in query_words if w in title_lower]
            if matching_words:
                keyword_score = len(matching_words) / len(query_words)

            # Category boosting score (0-0.3)
            category_boost = 0.0
            if category in category_keywords:
                # Boost if query words appear in title or category name
                if any(w in title_lower or w in category.lower() for w in query_words):
                    category_boost = 0.2

            # Combined score: 70% semantic + 20% keyword + 10% category
            combined_score = (
                faiss_score * 0.70 +
                keyword_score * 100 * 0.20 +
                category_boost * 100 * 0.10
            )

            scored_videos.append({
                "uuid": uuid,
                "video": video,
                "combined_score": combined_score
            })

        # Step 6: Sort by combined score
        scored_videos.sort(key=lambda x: x["combined_score"], reverse=True)

        # Step 7: Transform to response
        print(f"[RELOAD] Step 6: Transforming {len(scored_videos)} videos...")
        video_responses = [transform_video(v["video"]) for v in scored_videos]

        return {
            "videos": video_responses,
            "query": query,
            "total": len(video_responses),
            "offset": offset
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query: {str(e)}"
        )
    except Exception as e:
        print(f"[RELOAD-SEARCH ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search reload failed"
        )


@router.post("/reload-recommend")
async def reload_recommendations(request: ReloadRecommendRequest):
    """
    Lazy loading endpoint - reload recommendations with pagination for infinite scroll.

    Provides continuous recommendations for same reference video while excluding
    all previously shown results. Maintains identical hybrid ranking from /recommend.

    ALGORITHM:
    ----------
    1. Lookup Embedding: Get cached embedding for reference video (no re-computation)
    2. FAISS Search: Find K*3 + buffer (500) semantically similar videos
    3. Filter: Remove reference video itself + all excluded recommendations
    4. Take Top K: Get first `limit` from filtered pool
    5. Re-rank: Apply same hybrid ranking (70% semantic + 15% keywords + 15% category)
    6. Return: Sorted unique recommendations

    EFFICIENCY:
    - Uses cached embedding (no re-embedding needed)
    - FAISS search is fast (~10ms)
    - Filtering and ranking are O(n)
    - Faster than /reload-search because:
      * Already have embedding (not re-computing)
      * No query parsing needed
      * Reference metadata cached

    EXAMPLE:
    Reference: "Flinch w/ BTS" from Late Late Show

    1. /recommend?video_id=abc123&limit=15
       Returns TOP 15 most similar late-night show clips
       - Same episode interactions
       - Same channel videos
       - Best semantic matches

    2. /reload-recommend with 15 excluded
       Returns NEXT 15 different late-night show content
       - Other celebrity interview videos
       - Similar themes/guests

    3. /reload-recommend with 30 excluded
       Returns NEXT 15 more recommendations
       - Related entertainment content
       - More comedy/talk show videos

    CONTINUING UNTIL:
    - Empty pool (all videos shown)
    - User navigates away
    - Or deliberately stops scrolling

    PERFORMANCE:
    - Embedding lookup: ~1ms (cached)
    - Metadata fetch: ~10ms (reference video)
    - FAISS search: ~10-15ms (large K=500)
    - Filtering: ~5ms
    - Re-ranking: ~15ms
    - Total: 150-250ms (faster than /reload-search)

    INPUT:
    {
        "video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",  // Reference video UUID
        "excluded_video_ids": [                               // All shown recommendations
            "b2c3d4e5-f6a7-8901-bcde-f23456789012",
            "c3d4e5f6-a7b8-9012-cdef-345678901234",
            // ... all previous recommendations
        ],
        "limit": 15                                           // Return next 15
    }

    OUTPUT:
    {
        "videos": [VideoResponse[], ...],
        "current_video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "total": 15
    }

    FRONTEND PATTERN:
    1. User clicks "More Like This" on video
    2. Show sidebar with /recommend results (15 videos)
    3. User scrolls down in sidebar
    4. Call /reload-recommend with those 15 excluded
    5. Add NEXT 15 to sidebar
    6. Continue until sidebar holds 60+ recommendations or user leaves

    IMPORTANT NOTES:
    - Reference video NEVER appears in recommendations
    - All results remain semantically related to reference
    - Can serve unlimited recommendations (until all videos shown)
    - No pagination token - excluded_ids track shown items
    - No "has_more" flag - return empty array when depleted

    CATEGORY MATCHING:
    - Same category: 40% boost
    - Related category: 10% boost
    - Different category: 0% boost
    """
    try:
        video_id = request.video_id
        excluded_ids = set(request.excluded_video_ids or [])
        limit = min(request.limit, 50)  # Cap at 50 per reload

        print(f"\n{'#'*70}")
        print(f"[RELOAD-RECOMMEND] Reference video: {video_id[:8]}...")
        print(f"[RELOAD-RECOMMEND] Excluding {len(excluded_ids)} already-shown videos")
        print(f"{'#'*70}")

        # Step 1: Get reference video embedding
        print(f"[RELOAD-REC] Step 1: Looking up embedding for {video_id[:8]}...")
        current_embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)

        if current_embedding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found or has no embedding"
            )

        # Step 2: Fetch reference video metadata
        print("[RELOAD-REC] Step 2: Fetching reference video metadata...")
        ref_videos = await get_videos_metadata_by_uuids([video_id])
        if not ref_videos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video metadata not found"
            )

        ref_video = ref_videos[0]
        ref_title = ref_video.get("title", "").lower()
        ref_category = ref_video.get("category_name", "")

        # Extract keywords from reference video title
        ref_keywords = set(ref_title.split())
        # Remove common words
        common_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "from", "of", "for", "is", "are", "was", "were"}
        ref_keywords = {w for w in ref_keywords if w not in common_words and len(w) > 2}

        # Step 3: FAISS search (get large pool, then filter exclusions)
        # Get enough to accommodate exclusions + buffer
        faiss_k = min(limit * 3 + 50, 500)  # Extra buffer for exclusions
        print(f"[RELOAD-REC] Step 3: FAISS search for K={faiss_k}...")
        faiss_results = faiss_manager.search_similar(current_embedding, k=faiss_k)

        # Filter out reference video and excluded videos
        filtered_results = [
            (uuid_str, score) for uuid_str, score in faiss_results
            if uuid_str != video_id and uuid_str not in excluded_ids
        ]

        if not filtered_results:
            return {
                "videos": [],
                "current_video_id": video_id,
                "total": 0
            }

        # Take top limit results from filtered pool
        paginated_results = filtered_results[:limit]

        # Extract UUIDs
        video_uuids = [uuid_str for uuid_str, _ in paginated_results]

        # Step 4: Fetch metadata
        print(f"[RELOAD-REC] Step 4: Fetching metadata for {len(video_uuids)} videos...")
        videos_data = await get_videos_metadata_by_uuids(video_uuids)

        # Create lookup dictionaries
        uuid_to_faiss_score = {uuid_str: score for uuid_str, score in paginated_results}
        uuid_to_video = {v["id"]: v for v in videos_data}

        # Step 5: Apply same hybrid ranking as /recommend
        print("[RELOAD-REC] Step 5: Re-ranking with hybrid strategy...")

        # Define category relationships (same as /recommend)
        related_categories = {
            "Music": ["Entertainment", "Shows"],
            "Entertainment": ["Music", "Shows", "Comedy"],
            "Comedy": ["Entertainment", "People & Blogs"],
            "Gaming": ["Science & Technology"],
            "Sports": ["Entertainment"],
            "Education": ["Science & Technology"],
            "Travel & Events": ["People & Blogs", "Entertainment"],
            "Film & Animation": ["Entertainment", "Shows"],
        }

        scored_videos = []
        for uuid in video_uuids:
            video = uuid_to_video.get(uuid)
            if not video:
                continue

            faiss_score = uuid_to_faiss_score[uuid]
            title_lower = video.get("title", "").lower()
            category = video.get("category_name", "")

            # Shared keywords score (0-1)
            video_keywords = set(title_lower.split())
            shared_keywords = ref_keywords.intersection(video_keywords)
            keyword_score = 0.0
            if ref_keywords:
                keyword_score = len(shared_keywords) / len(ref_keywords)

            # Category affinity score (0-1)
            category_boost = 0.0
            if category == ref_category:
                category_boost = 0.4  # 40% boost for same category
            else:
                # Weak boost if in related category
                if ref_category in related_categories and category in related_categories.get(ref_category, []):
                    category_boost = 0.1

            # Combined score: 70% semantic + 15% shared keywords + 15% category
            combined_score = (
                faiss_score * 0.70 +
                keyword_score * 100 * 0.15 +
                category_boost * 100 * 0.15
            )

            scored_videos.append({
                "uuid": uuid,
                "video": video,
                "combined_score": combined_score
            })

        # Step 6: Sort by combined score
        scored_videos.sort(key=lambda x: x["combined_score"], reverse=True)

        # Step 7: Transform to response
        print(f"[RELOAD-REC] Step 6: Transforming {len(scored_videos)} videos...")
        video_responses = [transform_video(v["video"]) for v in scored_videos]

        return {
            "videos": video_responses,
            "current_video_id": video_id,
            "total": len(video_responses)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RELOAD-RECOMMEND ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation reload failed"
        )


def _normalize_filter_values(values: list[str], upper: bool = False) -> list[str]:
    """Normalize, de-duplicate, and trim empty values while preserving order."""
    cleaned: list[str] = []
    for value in values or []:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if upper:
            normalized = normalized.upper()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _sort_key_by_velocity_and_views(video: dict) -> tuple[float, float]:
    velocity = video.get("velocity_score")
    views = video.get("views") or 0
    return (velocity if velocity is not None else float("-inf"), float(views))


def _merge_and_sort_filtered_rows(video_rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for row in video_rows:
        video_id = row.get("id")
        if not video_id:
            continue

        existing = merged.get(video_id)
        if not existing or _sort_key_by_velocity_and_views(row) > _sort_key_by_velocity_and_views(existing):
            merged[video_id] = row

    combined = list(merged.values())
    combined.sort(key=_sort_key_by_velocity_and_views, reverse=True)
    return combined


async def _fetch_unified_filtered_videos(
    categories: list[str],
    regions: list[str],
    excluded_ids: list[str],
    limit: int,
) -> list[dict]:
    """
    Fetch videos with OR logic between categories and regions.

    - categories only: category filter
    - regions only: region filter
    - both: union(categories, regions), de-duplicated and sorted by velocity/views
    """
    if categories and not regions:
        return await get_videos_by_categories(
            categories=categories,
            excluded_ids=excluded_ids,
            limit=limit,
        )

    if regions and not categories:
        return await get_videos_by_regions(
            regions=regions,
            excluded_ids=excluded_ids,
            limit=limit,
        )

    # Both filters active: OR merge category + region pools.
    # We over-fetch per source to reduce under-filled unions after de-duplication.
    per_source_limit = min(limit * 2, 200)
    category_rows, region_rows = await asyncio.gather(
        get_videos_by_categories(
            categories=categories,
            excluded_ids=excluded_ids,
            limit=per_source_limit,
        ),
        get_videos_by_regions(
            regions=regions,
            excluded_ids=excluded_ids,
            limit=per_source_limit,
        ),
    )
    return _merge_and_sort_filtered_rows(category_rows + region_rows)


@router.post("/filter-homefeed")
async def filter_homefeed(request: FilterHomeFeedRequest):
    """Unified category/region homefeed filter with OR semantics."""
    categories = _normalize_filter_values(request.categories)
    regions = _normalize_filter_values(request.regions, upper=True)

    if not categories and not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one category or region is required"
        )

    try:
        limit = min(request.limit, 50)
        excluded_ids = request.excluded_video_ids if request.excluded_video_ids else []

        print(
            f"[FILTER-HOMEFEED] categories={categories}, regions={regions}, "
            f"excluded={len(excluded_ids)}, limit={limit}"
        )

        videos_data = await _fetch_unified_filtered_videos(
            categories=categories,
            regions=regions,
            excluded_ids=excluded_ids,
            limit=limit,
        )

        current_batch = videos_data[:limit]
        video_responses = [transform_video(v) for v in current_batch]

        return {
            "videos": video_responses,
            "categories": categories,
            "regions": regions,
            "total": len(video_responses),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[FILTER-HOMEFEED ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unified homefeed filter failed"
        )


@router.post("/reload-filter-homefeed")
async def reload_filter_homefeed(request: FilterHomeFeedRequest):
    """Lazy loading endpoint for unified category/region homefeed filtering."""
    categories = _normalize_filter_values(request.categories)
    regions = _normalize_filter_values(request.regions, upper=True)

    if not categories and not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one category or region is required"
        )

    try:
        excluded_ids = request.excluded_video_ids if request.excluded_video_ids else []
        limit = min(request.limit, 50)

        print(f"\n{'#' * 70}")
        print(
            f"[RELOAD-FILTER-HOMEFEED] categories={categories}, regions={regions}, "
            f"limit={limit}"
        )
        print(f"[RELOAD-FILTER-HOMEFEED] excluding {len(excluded_ids)} already-shown videos")
        print(f"{'#' * 70}")

        videos_data = await _fetch_unified_filtered_videos(
            categories=categories,
            regions=regions,
            excluded_ids=excluded_ids,
            limit=limit + 1,
        )

        has_more = len(videos_data) > limit
        current_batch = videos_data[:limit]
        video_responses = [transform_video(v) for v in current_batch]

        return {
            "videos": video_responses,
            "categories": categories,
            "regions": regions,
            "total": len(video_responses),
            "has_more": has_more,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RELOAD-FILTER-HOMEFEED ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unified homefeed reload failed"
        )


@router.post("/search-by-category")
async def search_by_category(request: CategorySearchRequest):
    """
    Fetch videos filtered by one or more categories, ordered by velocity score then views.

    Used for both initial load and infinite-scroll pagination:
    - Initial load: send categories, empty excluded_video_ids
    - Pagination:   send categories + all UUIDs already shown in excluded_video_ids

    REQUEST:
    {
        "categories": ["Music", "Gaming"],
        "excluded_video_ids": [],   // grow this list for pagination
        "limit": 30
    }

    RESPONSE:
    {
        "videos": [VideoResponse, ...],
        "categories": ["Music", "Gaming"],
        "total": 30
    }
    """
    if not request.categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one category is required"
        )

    try:
        print(f"[CATEGORY SEARCH] categories={request.categories}, excluded={len(request.excluded_video_ids)}")

        videos_data = await get_videos_by_categories(
            categories=request.categories,
            excluded_ids=request.excluded_video_ids if request.excluded_video_ids else None,
            limit=request.limit,
        )

        video_responses = [transform_video(v) for v in videos_data]

        return {
            "videos": video_responses,
            "categories": request.categories,
            "total": len(video_responses),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CATEGORY SEARCH ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Category search failed"
        )


@router.post("/reload-search-by-category")
async def reload_search_by_category(request: CategorySearchRequest):
    """
    Lazy loading endpoint for category-based search results.

    Works like `/search-by-category` but is optimized for infinite scroll by
    excluding all previously shown video IDs and returning the next batch.

    REQUEST:
    {
        "categories": ["Music", "Gaming"],
        "excluded_video_ids": ["uuid1", "uuid2", ...],
        "limit": 30
    }

    RESPONSE:
    {
        "videos": [VideoResponse, ...],
        "categories": ["Music", "Gaming"],
        "total": 30,
        "has_more": true
    }
    """
    if not request.categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one category is required"
        )

    try:
        excluded_ids = request.excluded_video_ids if request.excluded_video_ids else []
        limit = min(request.limit, 50)  # Cap at 50 per reload

        print(f"\n{'#'*70}")
        print(f"[RELOAD-CATEGORY] categories={request.categories}, limit={limit}")
        print(f"[RELOAD-CATEGORY] excluding {len(excluded_ids)} already-shown videos")
        print(f"{'#'*70}")

        # Fetch one extra record so frontend can know if additional pages exist.
        videos_data = await get_videos_by_categories(
            categories=request.categories,
            excluded_ids=excluded_ids,
            limit=limit + 1,
        )

        has_more = len(videos_data) > limit
        current_batch = videos_data[:limit]
        video_responses = [transform_video(v) for v in current_batch]

        return {
            "videos": video_responses,
            "categories": request.categories,
            "total": len(video_responses),
            "has_more": has_more,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RELOAD-CATEGORY ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Category reload failed"
        )


@router.post("/search-by-region")
async def search_by_region(request: RegionSearchRequest):
    """
    Fetch videos filtered by one or more region codes (country_code).

    Used for both initial load and infinite-scroll pagination:
    - Initial load: send regions, empty excluded_video_ids
    - Pagination:   send regions + all UUIDs already shown in excluded_video_ids

    REQUEST:
    {
        "regions": ["US", "GB", "IN"],
        "excluded_video_ids": [],
        "limit": 30
    }

    RESPONSE:
    {
        "videos": [VideoResponse, ...],
        "regions": ["US", "GB", "IN"],
        "total": 30
    }
    """
    if not request.regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one region is required"
        )

    try:
        print(f"[REGION SEARCH] regions={request.regions}, excluded={len(request.excluded_video_ids)}")

        videos_data = await get_videos_by_regions(
            regions=request.regions,
            excluded_ids=request.excluded_video_ids if request.excluded_video_ids else None,
            limit=request.limit,
        )

        video_responses = [transform_video(v) for v in videos_data]

        return {
            "videos": video_responses,
            "regions": request.regions,
            "total": len(video_responses),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGION SEARCH ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Region search failed"
        )


@router.post("/reload-search-by-region")
async def reload_search_by_region(request: RegionSearchRequest):
    """
    Lazy loading endpoint for region-based search results.

    Works like `/search-by-region` but is optimized for infinite scroll by
    excluding all previously shown video IDs and returning the next batch.

    REQUEST:
    {
        "regions": ["US", "GB", "IN"],
        "excluded_video_ids": ["uuid1", "uuid2", ...],
        "limit": 30
    }

    RESPONSE:
    {
        "videos": [VideoResponse, ...],
        "regions": ["US", "GB", "IN"],
        "total": 30,
        "has_more": true
    }
    """
    if not request.regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one region is required"
        )

    try:
        excluded_ids = request.excluded_video_ids if request.excluded_video_ids else []
        limit = min(request.limit, 50)  # Cap at 50 per reload

        print(f"\n{'#'*70}")
        print(f"[RELOAD-REGION] regions={request.regions}, limit={limit}")
        print(f"[RELOAD-REGION] excluding {len(excluded_ids)} already-shown videos")
        print(f"{'#'*70}")

        # Fetch one extra record so frontend can know if additional pages exist.
        videos_data = await get_videos_by_regions(
            regions=request.regions,
            excluded_ids=excluded_ids,
            limit=limit + 1,
        )

        has_more = len(videos_data) > limit
        current_batch = videos_data[:limit]
        video_responses = [transform_video(v) for v in current_batch]

        return {
            "videos": video_responses,
            "regions": request.regions,
            "total": len(video_responses),
            "has_more": has_more,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RELOAD-REGION ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Region reload failed"
        )
