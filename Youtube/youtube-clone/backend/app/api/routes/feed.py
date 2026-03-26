from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional
from app.api.deps import get_current_user
from app.db import get_user_by_id
from app.schemas.feed import (
    FeedResponse, VideoResponse, ChannelInfo, CategoriesResponse,
    LikeVideoRequest, LikeResponse, LikesListResponse,
    DislikeVideoRequest, DislikeResponse, DislikesListResponse
)
from app.core.recommendation import (
    build_taste_vector_from_uuids,
    generate_phase1_feed,
    generate_phase2_feed,
    generate_phase3_feed
)
from app.db import (
    get_watch_history, get_unique_categories,
    get_user_liked_videos, add_like, remove_like, is_video_liked,
    get_user_disliked_videos, add_dislike, remove_dislike, is_video_disliked
)
from app.utils.formatters import format_views, format_timestamp, generate_channel_avatar, is_verified

router = APIRouter()


def transform_video(video: dict) -> VideoResponse:
    """Transform DB row to VideoResponse"""
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


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    region: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    Authenticated user feed endpoint with advanced personalization.

    Features:
    1. Fetches user's watch history with recency & duration weighting
    2. Auto-determines personalization phase (Cold Start → Warm-Up → Personalized)
    3. Adaptive bucket allocation based on interaction count
    4. Deduplication: No video appears more than once
    5. Watch history filter: Max 10% of recommendations from watched videos
    6. User region preference: Falls back to provided region if not set
    7. Semantic search + trending mix for diversity

    Personalization Phases:
    - Phase 1 (0 interactions): 50/50 global/local trending
    - Phase 2 (1-4 interactions): 20-40% semantic search + trending
    - Phase 3 (5+ interactions): 60-75% semantic same-region + buckets

    Args:
        region: Optional region override (defaults to user's saved region)
        limit: Number of videos to return (1-50)
        current_user: Authenticated user from JWT

    Returns:
        FeedResponse with videos, strategy, interaction count, and total
    """
    user_id = current_user["id"]

    # Fetch user profile for region preference
    db_user = await get_user_by_id(user_id)
    user_region = region or (db_user.get("region") if db_user else None) or "US"

    # Fetch user's watch history with timestamps and duration
    try:
        history_rows = await get_watch_history(user_id, limit=100)
        watched_uuids = [row["video_id"] for row in history_rows]  # videos.id UUIDs
    except Exception as e:
        print(f"[WARNING] Failed to fetch watch history for user {user_id}: {e}")
        history_rows = []
        watched_uuids = []

    interaction_count = len(watched_uuids)

    # Determine phase and generate feed with fully applied filters
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        videos = await generate_phase1_feed(user_region, watched_uuids, limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        # Build taste vector with recency + duration weighting
        taste = await build_taste_vector_from_uuids(
            watched_uuids,
            watch_history=history_rows,
            use_recency_weighting=True
        )
        videos = await generate_phase2_feed(
            taste, user_region, watched_uuids, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, watched_uuids, limit)

    else:  # 5+ interactions - Fully personalized
        strategy = "phase_3_personalized"
        # Build taste vector with recency + duration weighting
        taste = await build_taste_vector_from_uuids(
            watched_uuids,
            watch_history=history_rows,
            use_recency_weighting=True
        )
        videos = await generate_phase3_feed(
            taste, user_region, watched_uuids, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, watched_uuids, limit)

    # Transform to response format
    video_responses = [transform_video(v) for v in videos]

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )
    
    
    
    
    


@router.get("/trending", response_model=FeedResponse)
async def get_trending_feed(
    region: str = Query(default="US"),
    limit: int = Query(default=30, ge=1, le=50)
):
    """
    Global trending feed (no personalization, no auth required).

    Returns trending videos based on velocity_score in specified region.
    """
    videos = await generate_phase1_feed(region, [], limit)
    video_responses = [transform_video(v) for v in videos]

    return FeedResponse(
        videos=video_responses,
        strategy="trending_only",
        interaction_count=0,
        total=len(video_responses)
    )


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories():
    """Fetch unique categories"""
    categories = await get_unique_categories()
    return CategoriesResponse(categories=["All"] + categories)


@router.get("/personalization-debug")
async def debug_personalization(current_user: dict = Depends(get_current_user)):
    """
    DEBUG ENDPOINT: Return personalization state for authenticated user.

    Shows:
    - Interaction count (watch history size)
    - Current phase (Cold Start, Warm-Up, Personalized)
    - Which bucket allocation will be used
    - Region preference
    """
    user_id = current_user["id"]

    # Fetch user profile and watch history
    db_user = await get_user_by_id(user_id)
    history_rows = await get_watch_history(user_id, limit=100)
    interaction_count = len(history_rows)
    user_region = db_user.get("region") if db_user else "US"

    # Determine phase
    if interaction_count == 0:
        phase = "phase_1_cold_start"
        description = "50% Global Trending + 50% Local Trending"
    elif 1 <= interaction_count <= 4:
        if interaction_count <= 2:
            allocation = "20% Semantic + 50% Trending + 30% Local"
        else:
            allocation = "40% Semantic + 35% Trending + 25% Local"
        phase = "phase_2_warm_up"
        description = f"Warm-Up: {allocation}"
    else:  # 5+
        if interaction_count < 10:
            allocation = "60% Semantic Same-Region + 20% Foreign + 10% Local + 10% Global"
        elif interaction_count < 20:
            allocation = "70% Semantic Same-Region + 15% Foreign + 10% Local + 5% Global"
        else:
            allocation = "75% Semantic Same-Region + 15% Foreign + 7% Local + 3% Global"
        phase = "phase_3_personalized"
        description = f"Personalized: {allocation}"

    return {
        "user_id": user_id,
        "interaction_count": interaction_count,
        "phase": phase,
        "description": description,
        "region": user_region,
        "watch_history_size": len(history_rows),
        "recent_watches": [
            {
                "video_id": row["video_id"],
                "duration_seconds": row.get("watch_duration_seconds", 0),
                "watched_at": row.get("started_at")
            }
            for row in history_rows[:5]
        ]
    }


# ======================== LIKES ENDPOINTS ========================


@router.get("/likes", response_model=LikesListResponse)
async def get_liked_videos(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all videos liked by the authenticated user.

    Features:
    - Returns liked videos in reverse chronological order (newest first)
    - Includes full video metadata
    - Pageable with configurable limit (1-500)

    Args:
        limit: Number of liked videos to return (default 50, max 500)
        current_user: Authenticated user from JWT

    Returns:
        LikesListResponse with array of VideoResponse and total count
    """
    user_id = current_user["id"]

    try:
        # Fetch liked videos from database
        liked_videos = await get_user_liked_videos(user_id, limit=limit)

        # Transform to response format
        video_responses = [transform_video(v) for v in liked_videos]

        return LikesListResponse(
            videos=video_responses,
            total=len(video_responses)
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch liked videos for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch liked videos"
        )


@router.post("/like", response_model=LikeResponse)
async def like_video(
    request: LikeVideoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Like a video (add to user's liked collection).

    Features:
    - Idempotent: Liking the same video twice is safe (no duplicate)
    - Returns current like state after action
    - Validates user authentication

    Args:
        request: Contains video_uuid to like
        current_user: Authenticated user from JWT

    Returns:
        LikeResponse with success status and current like state
    """
    user_id = current_user["id"]
    video_id = request.video_uuid

    print(f"[DEBUG] like_video called - user_id: {user_id}, video_id: {video_id}")

    try:
        # Add like (safe if already liked)
        success = await add_like(user_id, video_id)

        print(f"[DEBUG] add_like result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add like - check backend logs for details"
            )

        # Return current state
        is_liked = await is_video_liked(user_id, video_id)

        print(f"[DEBUG] is_video_liked result: {is_liked}")

        return LikeResponse(
            success=True,
            message="Video liked successfully",
            is_liked=is_liked
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] like_video exception - user_id: {user_id}, video_id: {video_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to like video: {str(e)}"
        )


@router.delete("/like", response_model=LikeResponse)
async def unlike_video(
    request: LikeVideoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Unlike a video (remove from user's liked collection).

    Features:
    - Idempotent: Unliking a non-liked video is safe
    - Removes like immediately
    - Returns updated like state

    Args:
        request: Contains video_uuid to unlike
        current_user: Authenticated user from JWT

    Returns:
        LikeResponse with success status and current like state (should be false)
    """
    user_id = current_user["id"]
    video_id = request.video_uuid

    print(f"[DEBUG] unlike_video called - user_id: {user_id}, video_id: {video_id}")

    try:
        # Remove like (safe if not already liked)
        success = await remove_like(user_id, video_id)

        print(f"[DEBUG] remove_like result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove like"
            )

        # Verify like was removed
        is_liked = await is_video_liked(user_id, video_id)

        print(f"[DEBUG] is_video_liked after removal: {is_liked}")

        return LikeResponse(
            success=True,
            message="Video unliked successfully",
            is_liked=is_liked
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to unlike video {video_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlike video: {str(e)}"
        )


@router.get("/dislikes", response_model=DislikesListResponse)
async def get_disliked_videos(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all videos disliked by authenticated user.

    Args:
        limit: Maximum number of disliked videos to return (default 50, max 500)
        current_user: Authenticated user from JWT

    Returns:
        DislikesListResponse with list of disliked videos and total count
    """
    user_id = current_user["id"]

    try:
        # Fetch user's disliked videos
        videos = await get_user_disliked_videos(user_id, limit)

        if not videos:
            return DislikesListResponse(videos=[], total=0)

        # Transform to VideoResponse format
        video_responses = [transform_video(video) for video in videos]

        return DislikesListResponse(
            videos=video_responses,
            total=len(video_responses)
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch disliked videos for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch disliked videos"
        )


@router.post("/dislike", response_model=DislikeResponse)
async def dislike_video(
    request: DislikeVideoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Dislike a video (add to user's disliked collection).

    Features:
    - Idempotent: Disliking the same video twice is safe (no duplicate)
    - Returns current dislike state after action
    - Validates user authentication

    Args:
        request: Contains video_uuid to dislike
        current_user: Authenticated user from JWT

    Returns:
        DislikeResponse with success status and current dislike state
    """
    user_id = current_user["id"]
    video_id = request.video_uuid

    print(f"[DEBUG] dislike_video called - user_id: {user_id}, video_id: {video_id}")

    try:
        # Add dislike (safe if already disliked)
        success = await add_dislike(user_id, video_id)

        print(f"[DEBUG] add_dislike result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add dislike - check backend logs for details"
            )

        # Return current state
        is_disliked = await is_video_disliked(user_id, video_id)

        print(f"[DEBUG] is_video_disliked result: {is_disliked}")

        return DislikeResponse(
            success=True,
            message="Video disliked successfully",
            is_disliked=is_disliked
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] dislike_video exception - user_id: {user_id}, video_id: {video_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dislike video: {str(e)}"
        )


@router.delete("/dislike", response_model=DislikeResponse)
async def remove_dislike_video(
    request: DislikeVideoRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove dislike from a video (remove from user's disliked collection).

    Features:
    - Idempotent: Removing dislike from a non-disliked video is safe
    - Removes dislike immediately
    - Returns updated dislike state

    Args:
        request: Contains video_uuid to remove dislike from
        current_user: Authenticated user from JWT

    Returns:
        DislikeResponse with success status and current dislike state (should be false)
    """
    user_id = current_user["id"]
    video_id = request.video_uuid

    print(f"[DEBUG] remove_dislike_video called - user_id: {user_id}, video_id: {video_id}")

    try:
        # Remove dislike (safe if not already disliked)
        success = await remove_dislike(user_id, video_id)

        print(f"[DEBUG] remove_dislike result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove dislike"
            )

        # Verify dislike was removed
        is_disliked = await is_video_disliked(user_id, video_id)

        print(f"[DEBUG] is_video_disliked after removal: {is_disliked}")

        return DislikeResponse(
            success=True,
            message="Video dislike removed successfully",
            is_disliked=is_disliked
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to remove dislike for video {video_id} and user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove dislike: {str(e)}"
        )
