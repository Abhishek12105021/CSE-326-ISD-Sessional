"""
Search and recommendation endpoints.

Leverages FAISS for fast similarity search on embedded queries and videos.

Endpoints:
- POST /search?q=query&limit=50  → Search by text query
- POST /recommend?video_id=uuid&limit=15 → Find similar videos
"""
from fastapi import APIRouter, Query, HTTPException, status
import numpy as np
from uuid import UUID
from typing import Optional

from app.core import embedding_service, faiss_manager
from app.db import get_videos_metadata_by_uuids
from app.schemas.feed import VideoResponse, ChannelInfo
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
    Hybrid recommendations: Semantic similarity + Shared keywords + Category affinity.

    Process:
    1. Get reference video embedding from FAISS cache
    2. Fetch reference video metadata (title, category)
    3. FAISS search for K*2 similar videos (expanded pool)
    4. Shared keywords: Boost if result shares keywords with reference video
    5. Category affinity: Strong boost if same category as reference
    6. Re-rank by combined score (semantic + keywords + category)
    7. Return top K recommendations

    Args:
        video_id: Reference video UUID (e.g., "550e8400-e29b-41d4...")
        limit: Number of recommendations (1-50)

    Returns:
        {
            "videos": [VideoResponse, ...],
            "current_video_id": reference video UUID,
            "total": number of recommendations
        }
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
