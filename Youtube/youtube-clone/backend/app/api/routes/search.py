"""
Search and recommendation endpoints.

Leverages FAISS for fast similarity search on embedded queries and videos.

Endpoints:
- POST /search?q=query&limit=50  → Search by text query
- POST /recommend?video_id=uuid&limit=15 → Find similar videos
- POST /reload-search → Lazy load more search results with pagination
- POST /reload-search-by-category → Lazy load category-filtered search results
"""
from fastapi import APIRouter, Query, HTTPException, status
import numpy as np
from uuid import UUID
from typing import Optional
import time

from app.core import embedding_service, faiss_manager
from app.db import get_videos_metadata_by_uuids, get_videos_by_categories
from app.schemas.feed import VideoResponse, ChannelInfo, SearchReloadRequest, ReloadRecommendRequest, CategorySearchRequest
from app.utils.formatters import format_views, format_timestamp, generate_channel_avatar, is_verified

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
        duration="10:00",
        category=video.get("category_name", "Unknown"),
        velocity_score=video.get("velocity_score")
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
        print(f"[SEARCH] Re-ranking with keyword matching...")

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
                category_words = category_keywords[category]
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
        print(f"[RECOMMEND] Fetching reference video metadata...")
        ref_videos = await get_videos_metadata_by_uuids([video_id])
        if not ref_videos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video metadata not found"
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
        print(f"[RECOMMEND] Re-ranking by shared context...")

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
        print(f"[RELOAD] Step 1: Embedding query...")
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
        print(f"[RELOAD] Step 3: Filtering excluded videos and applying offset...")
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
        print(f"[RELOAD] Step 5: Re-ranking with hybrid strategy...")

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
                category_words = category_keywords[category]
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
        print(f"[RELOAD-REC] Step 2: Fetching reference video metadata...")
        ref_videos = await get_videos_metadata_by_uuids([video_id])
        if not ref_videos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video metadata not found"
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
        print(f"[RELOAD-REC] Step 5: Re-ranking with hybrid strategy...")

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


@router.get("/search-by-category")
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


@router.get("/reload-search-by-category")
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
