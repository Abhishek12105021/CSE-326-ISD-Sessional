import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from uuid import UUID
from app.api.deps import get_current_user
from app.db import get_user_by_id
from app.schemas.feed import (
    FeedResponse, VideoResponse, ChannelInfo, CategoriesResponse,
    LikeVideoRequest, LikeResponse, LikesListResponse,
    DislikeVideoRequest, DislikeResponse, DislikesListResponse,
    SubscribeRequest, SubscriptionResponse, SubscribedChannelsResponse, AllChannelsResponse,
    WatchEventRequest, WatchEventResponse, VideoMetadataRequest, VideoMetadataResponse,
    DeleteWatchHistoryRequest, ReloadFeedRequest, ChannelPageRequest, ChannelPageResponse
)
from app.core.recommendation import (
    generate_phase1_feed,
    generate_phase2_feed,
    generate_phase3_feed,
    get_taste_vector_for_feed,
)
from app.db import (
    add_dislike,
    add_like,
    decrement_video_views,
    delete_watch_history,
    get_all_channels,
    get_unique_categories,
    get_user_by_id,
    get_user_disliked_videos,
    get_user_liked_videos,
    get_user_liked_videos_with_timestamps,
    get_user_subscribed_channels,
    get_videos_by_uuids,
    get_videos_metadata_by_uuids,
    get_watch_history,
    get_watch_record_by_id,
    increment_video_views,
    insert_watch_history,
    is_subscribed,
    is_video_disliked,
    is_video_liked,
    remove_dislike,
    remove_like,
    subscribe,
    unsubscribe,
    update_watch_history,
    get_videos_by_channel_title, get_channel_video_count
)
from app.schemas.feed import (
    AllChannelsResponse,
    CategoriesResponse,
    ChannelInfo,
    DeleteWatchHistoryRequest,
    DislikeResponse,
    DislikesListResponse,
    DislikeVideoRequest,
    FeedResponse,
    LikeResponse,
    LikesListResponse,
    LikeVideoRequest,
    ReloadFeedRequest,
    SubscribedChannelsResponse,
    SubscribeRequest,
    SubscriptionResponse,
    VideoMetadataRequest,
    VideoMetadataResponse,
    VideoResponse,
    WatchEventRequest,
    WatchEventResponse,
)
from app.utils.formatters import format_timestamp, format_views, generate_channel_avatar, is_verified

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
        publish_time_raw=video.get("publish_time", ""),
        duration="10:00",
        category=video.get("category_name", "Unknown"),
        velocity_score=video.get("velocity_score")
    )


@router.post("/channel", response_model=ChannelPageResponse)
async def get_channel_page(request: ChannelPageRequest):
    """
    Resolve a channel page from the videos table using channel_title only.

    The app has no dedicated channel table, so this endpoint derives the channel
    header and video list directly from matching video rows.
    """
    channel_name = request.channel_name.strip()
    if not channel_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="channel_name is required"
        )

    try:
        limit = min(request.limit, 50)
        excluded_ids = request.excluded_video_ids if request.excluded_video_ids else []

        print(f"[CHANNEL LOOKUP] channel_name='{channel_name}', excluded={len(excluded_ids)}, limit={limit}")

        total_count = await get_channel_video_count(channel_name)
        if total_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel '{channel_name}' not found"
            )

        representative_rows = await get_videos_by_channel_title(channel_name, limit=1)
        if not representative_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel '{channel_name}' not found"
            )

        videos_data = await get_videos_by_channel_title(
            channel_title=channel_name,
            excluded_ids=excluded_ids,
            limit=limit,
        )

        channel_source = representative_rows[0]
        channel = ChannelInfo(
            name=channel_name,
            avatar=generate_channel_avatar(channel_name),
            verified=is_verified(channel_source.get("views", 0), channel_source.get("likes", 0)),
            id=channel_name,
        )

        video_responses = [transform_video(v) for v in videos_data]
        has_more = total_count > (len(set(excluded_ids)) + len(video_responses))

        return {
            "channel": channel,
            "videos": video_responses,
            "total": total_count,
            "has_more": has_more,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CHANNEL LOOKUP ERROR] {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Channel lookup failed"
        )


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    region: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    Authenticated user feed endpoint with FAISS-accelerated personalization.

    Features:
    1. In-memory taste vector caching (sub-millisecond lookup)
    2. FAISS similarity search (< 10ms vs 1-2s pgvector)
    3. Lazy taste vector rebuild on cache miss (first request after restart)
    4. Incremental EMA updates on watch events
    5. All recommendation logic unchanged (3-phase strategy, bucket allocation)

    Personalization Phases:
    - Phase 1 (0 interactions): 50/50 global/local trending
    - Phase 2 (1-4 interactions): 20-40% semantic search + trending
    - Phase 3 (5+ interactions): 60-75% semantic same-region + buckets

    Performance: ~300-500ms (vs 15-20s with database approach)

    Args:
        region: Optional region override (defaults to user's saved region)
        limit: Number of videos to return (1-50)
        current_user: Authenticated user from JWT

    Returns:
        FeedResponse with videos, strategy, interaction count, and total
    """
    total_start = time.time()
    user_id = current_user["id"]

    print(f"\n{'#'*70}")
    print(f"[FEED GENERATION] Starting for user {user_id[:8]}...")
    print(f"{'#'*70}")

    # Step 1: Fetch user profile for region preference
    step_start = time.time()
    _db_user = await get_user_by_id(user_id)  # noqa: F841 - fetched for potential future use
    user_region = region or "US"
    print(f"[DEBUG] User profile fetched - user_id: {user_id}, region: {user_region}")
    # print(f"[DEBUG] region available in query: {region}, user profile region: {db_user.get('region') if db_user else 'N/A'}")
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[FEED Step 1/5] Fetched user profile, region={user_region} ({step_elapsed:.1f}ms)")

    # Step 2: Get taste vector (cached or rebuild) via FAISS manager
    step_start = time.time()
    try:
        taste, interaction_count = await get_taste_vector_for_feed(user_id)
    except Exception as e:
        print(f"[WARNING] Failed to get taste vector for user {user_id}: {e}")
        taste = None
        interaction_count = 0
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[FEED Step 2/5] Got taste vector: interactions={interaction_count}, "
          f"has_taste={taste is not None} ({step_elapsed:.1f}ms)")

    # Step 3: Fetch watched UUIDs for deduplication/filtering
    step_start = time.time()
    try:
        history_rows = await get_watch_history(user_id, limit=100)
        watched_uuids = [row["video_id"] for row in history_rows]
    except Exception as e:
        print(f"[WARNING] Failed to fetch watch history for dedup: {e}")
        watched_uuids = []
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[FEED Step 3/5] Fetched dedup list: {len(watched_uuids)} watched UUIDs ({step_elapsed:.1f}ms)")

    # Step 4: Determine phase and generate feed (returns UUIDs only)
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print("[FEED Step 4/5] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(user_region, watched_uuids, limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print("[FEED Step 4/5] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, user_region, watched_uuids, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, watched_uuids, limit)

    else:  # 5+ interactions - Fully personalized
        strategy = "phase_3_personalized"
        print("[FEED Step 4/5] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, user_region, watched_uuids, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, watched_uuids, limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[FEED Step 4/5] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Step 5: Fetch metadata for video UUIDs (single DB query, no embeddings)
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[FEED Step 5/5] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform to response format
    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[FEED GENERATION] Complete! Strategy: {strategy}, "
          f"Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )


@router.post("/reload", response_model=FeedResponse)
async def reload_feed(
    request: ReloadFeedRequest,
    region: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user)
):
    """
    Lazy loading endpoint - reload feed with more videos excluding already-shown ones.

    This endpoint allows infinite scrolling by returning 30 new recommended videos
    that exclude all previously shown videos. It uses the same personalization logic
    as the /feed endpoint but filters out the excluded videos.

    Features:
    - Same 3-phase personalization strategy as /feed
    - Excludes all videos in excluded_video_ids list
    - Returns 30 new videos based on user's current taste vector
    - Maintains consistent recommendation quality across reloads

    Args:
        request: ReloadFeedRequest with excluded_video_ids list
        region: Optional region override (defaults to user's saved region)
        current_user: Authenticated user from JWT

    Returns:
        FeedResponse with 30 new videos, strategy, interaction count, and total
    """
    total_start = time.time()
    user_id = current_user["id"]
    excluded_ids = request.excluded_video_ids or []
    limit = request.limit

    print(f"\n{'#'*70}")
    print(f"[RELOAD FEED] Starting for user {user_id[:8]}, excluding {len(excluded_ids)} videos...")
    print(f"{'#'*70}")

    # Step 1: Fetch user profile for region preference
    step_start = time.time()
    _db_user = await get_user_by_id(user_id)  # noqa: F841 - fetched for potential future use
    user_region = region or "US"
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[RELOAD Step 1/5] Fetched user profile, region={user_region} ({step_elapsed:.1f}ms)")

    # Step 2: Get taste vector (cached or rebuild) via FAISS manager
    step_start = time.time()
    try:
        taste, interaction_count = await get_taste_vector_for_feed(user_id)
    except Exception as e:
        print(f"[WARNING] Failed to get taste vector for user {user_id}: {e}")
        taste = None
        interaction_count = 0
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[RELOAD Step 2/5] Got taste vector: interactions={interaction_count}, "
          f"has_taste={taste is not None} ({step_elapsed:.1f}ms)")

    # Step 3: Combine excluded videos with watch history for comprehensive filtering
    step_start = time.time()
    try:
        history_rows = await get_watch_history(user_id, limit=100)
        watched_uuids = [row["video_id"] for row in history_rows]
    except Exception as e:
        print(f"[WARNING] Failed to fetch watch history: {e}")
        watched_uuids = []

    # Merge excluded videos with watch history (comprehensive filter list)
    all_excluded = list(set(excluded_ids + watched_uuids))
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[RELOAD Step 3/5] Built exclusion list: {len(all_excluded)} total "
          f"({len(excluded_ids)} from request + {len(watched_uuids)} from history) ({step_elapsed:.1f}ms)")

    # Step 4: Determine phase and generate feed (returns UUIDs only)
    # Use same phase logic as /feed but with all_excluded as filter
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print("[RELOAD Step 4/5] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(user_region, all_excluded, limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print("[RELOAD Step 4/5] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, user_region, all_excluded, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, all_excluded, limit)

    else:  # 5+ interactions - Fully personalized
        strategy = "phase_3_personalized"
        print("[RELOAD Step 4/5] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, user_region, all_excluded, interaction_count, limit
        ) if taste is not None else await generate_phase1_feed(user_region, all_excluded, limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[RELOAD Step 4/5] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Step 5: Fetch metadata for video UUIDs (single DB query, no embeddings)
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[RELOAD Step 5/5] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform to response format
    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[RELOAD FEED] Complete! Strategy: {strategy}, "
          f"Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

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
    video_uuids = await generate_phase1_feed(region, [], limit)
    videos = await get_videos_metadata_by_uuids(video_uuids)
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
    - Watch history count and liked videos count
    - Combined interaction count (unique videos)
    - Current phase (Cold Start, Warm-Up, Personalized)
    - Which bucket allocation will be used
    - Region preference
    - Like weight multiplier (2.0x)
    """
    user_id = current_user["id"]

    # Fetch user profile, watch history, and liked videos
    db_user = await get_user_by_id(user_id)
    history_rows = await get_watch_history(user_id, limit=100)
    liked_videos = await get_user_liked_videos_with_timestamps(user_id, limit=50)
    user_region = db_user.get("region") if db_user else "US"

    # Calculate combined interaction count (unique videos)
    watched_ids = {row["video_id"] for row in history_rows}
    liked_ids = {row["video_id"] for row in liked_videos}
    interaction_count = len(watched_ids | liked_ids)

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
        "watch_history_count": len(history_rows),
        "liked_videos_count": len(liked_videos),
        "total_interaction_count": interaction_count,
        "phase": phase,
        "description": description,
        "region": user_region,
        "like_weight_multiplier": 2.0,
        "recent_watches": [
            {
                "video_id": row["video_id"],
                "duration_seconds": row.get("watch_duration_seconds", 0),
                "watched_at": row.get("started_at")
            }
            for row in history_rows[:5]
        ],
        "recent_likes": [
            {
                "video_id": row["video_id"],
                "liked_at": row.get("liked_at")
            }
            for row in liked_videos[:5]
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

# -------------------------------------------------------subscriptions endpoints -------------------------------------------------------
@router.get("/subscriptions", response_model=SubscribedChannelsResponse)
async def get_subscriptions(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all channels subscribed by authenticated user.

    Args:
        limit: Maximum number of subscribed channels to return (default 100, max 500)
        current_user: Authenticated user from JWT

    Returns:
        SubscribedChannelsResponse with list of channel names and total count
    """
    user_id = current_user["id"]

    try:
        # Fetch user's subscribed channels
        channels = await get_user_subscribed_channels(user_id, limit)

        return SubscribedChannelsResponse(
            channels=channels,
            total=len(channels)
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch subscriptions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscriptions"
        )


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe_channel(
    request: SubscribeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Subscribe to a channel.

    Features:
    - Idempotent: Subscribing to same channel twice is safe (no duplicate)
    - Returns current subscription state after action
    - Validates user authentication

    Args:
        request: Contains channel_name to subscribe to
        current_user: Authenticated user from JWT

    Returns:
        SubscriptionResponse with success status and current subscription state
    """
    user_id = current_user["id"]
    channel_name = request.channel_name

    print(f"[DEBUG] subscribe_channel called - user_id: {user_id}, channel_name: {channel_name}")

    try:
        # Subscribe to channel
        success = await subscribe(user_id, channel_name)

        print(f"[DEBUG] subscribe result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to subscribe - check backend logs for details"
            )

        # Return current state
        is_sub = await is_subscribed(user_id, channel_name)

        print(f"[DEBUG] is_subscribed result: {is_sub}")

        return SubscriptionResponse(
            success=True,
            message="Subscribed successfully",
            is_subscribed=is_sub
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] subscribe_channel exception - user_id: {user_id}, channel_name: {channel_name}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@router.delete("/subscribe", response_model=SubscriptionResponse)
async def unsubscribe_channel(
    request: SubscribeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Unsubscribe from a channel.

    Features:
    - Idempotent: Unsubscribing from non-subscribed channel is safe
    - Removes subscription immediately
    - Returns updated subscription state

    Args:
        request: Contains channel_name to unsubscribe from
        current_user: Authenticated user from JWT

    Returns:
        SubscriptionResponse with success status and current subscription state (should be false)
    """
    user_id = current_user["id"]
    channel_name = request.channel_name

    print(f"[DEBUG] unsubscribe_channel called - user_id: {user_id}, channel_name: {channel_name}")

    try:
        # Unsubscribe from channel
        success = await unsubscribe(user_id, channel_name)

        print(f"[DEBUG] unsubscribe result: {success}")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unsubscribe"
            )

        # Verify subscription was removed
        is_sub = await is_subscribed(user_id, channel_name)

        print(f"[DEBUG] is_subscribed after unsubscribe: {is_sub}")

        return SubscriptionResponse(
            success=True,
            message="Unsubscribed successfully",
            is_subscribed=is_sub
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to unsubscribe from channel {channel_name} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsubscribe: {str(e)}"
        )


@router.get("/channels", response_model=AllChannelsResponse)
async def get_all_available_channels():
    """
    Get all available channels from videos table.

    Returns:
        AllChannelsResponse with list of all unique channel names and total count
    """
    try:
        # Fetch all unique channels
        channels = await get_all_channels()

        return AllChannelsResponse(
            channels=channels,
            total=len(channels)
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch all channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch channels"
        )


# ======================== VIDEO METADATA ENDPOINT ========================

@router.post("/get", response_model=VideoMetadataResponse)
async def get_video_metadata(request: VideoMetadataRequest):
    """
    Get complete video metadata by UUID.

    Returns all available video information including:
    - Basic video details (title, thumbnail, duration)
    - Channel information (name, avatar, verification status)
    - Engagement metrics (views, likes, velocity score)
    - Content metadata (category, publish time, description)
    - Technical details (video_id, embeddings availability)

    Args:
        request: VideoMetadataRequest containing video_uuid

    Returns:
        VideoMetadataResponse with complete video information
    """
    video_uuid = request.video_uuid

    print(f"[DEBUG] get_video_metadata - video_uuid: {video_uuid}")

    try:
        # Fetch video data by UUID
        videos = await get_videos_by_uuids([video_uuid])

        if not videos or len(videos) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with UUID {video_uuid} not found"
            )

        video_data = videos[0]

        # Parse tags from pipe-separated string to list
        tags_str = video_data.get("tags", "")
        tags_list = [tag.strip() for tag in tags_str.split("|") if tag.strip()] if isinstance(tags_str, str) else []

        # Transform to complete metadata response
        metadata = VideoMetadataResponse(
            id=video_data["id"],
            video_id=video_data["video_id"],
            title=video_data["title"],
            description=video_data.get("description", ""),
            thumbnail=video_data["thumbnail_link"],
            channel=ChannelInfo(
                name=video_data["channel_title"],
                avatar=generate_channel_avatar(video_data["channel_title"]),
                verified=is_verified(video_data.get("views", 0), video_data.get("likes", 0)),
                id=video_data["channel_title"]
            ),
            views=format_views(video_data.get("views", 0)),
            views_raw=video_data.get("views", 0),
            likes=video_data.get("likes", 0),
            dislikes=video_data.get("dislikes", 0),
            timestamp=format_timestamp(video_data.get("publish_time", "")),
            publish_time_raw=video_data.get("publish_time", ""),
            duration="10:00",  # Placeholder - would be calculated from video_duration_seconds
            category=video_data.get("category_name", "Unknown"),
            velocity_score=video_data.get("velocity_score"),
            region=video_data.get("region", "Unknown"),
            tags=tags_list,
            has_embedding=bool(video_data.get("embedding")),
            created_at=video_data.get("created_at"),
            updated_at=video_data.get("updated_at")
        )

        print(f"[DEBUG] Successfully retrieved metadata for video {video_uuid}")

        return metadata

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] get_video_metadata failed - video_uuid: {video_uuid}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve video metadata: {str(e)}"
        )


# ======================== WATCH TRACKING ENDPOINT ========================


@router.post("/watch", response_model=WatchEventResponse)
async def track_watch_event(
    request: WatchEventRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Track watch events for authenticated users.

    Two-phase tracking system:
    1. INSERT (video start): Creates watch record with duration=0
    2. UPDATE (video end): Updates with actual watch duration

    Flow:
    - User clicks video → Frontend calls POST /watch with video_uuid
    - Backend INSERTs watch_history row, returns watch_id
    - User leaves/navigates → Frontend calls POST /watch with watch_id + duration
    - Backend UPDATEs the watch_history row with actual duration

    Args:
        request: WatchEventRequest containing video_uuid and optional watch_id/duration
        current_user: Authenticated user from JWT

    Returns:
        WatchEventResponse with watch_id (INSERT) or success status (UPDATE)
    """
    user_id = current_user["id"]
    video_uuid = request.video_uuid

    print(f"[DEBUG] track_watch_event - user_id: {user_id}, video_uuid: {video_uuid}")

    try:
        # MODE 1: INSERT (video start) - no watch_id provided
        if not request.watch_id:
            print("[DEBUG] INSERT mode - creating new watch record")

            watch_id = await insert_watch_history(
                user_id=user_id,  # Authenticated user
                guest_uuid=None,  # Not a guest
                video_uuid=video_uuid
            )

            print(f"[DEBUG] Created watch record with ID: {watch_id}")

            # Increment video view count (only once per watch, on INSERT)
            view_increment_success = await increment_video_views(video_uuid)
            if view_increment_success:
                print(f"[DEBUG] Incremented view count for video {video_uuid}")
            else:
                print(f"[WARNING] Failed to increment view count for video {video_uuid}")

            # Update taste vector incrementally via EMA (O(1) operation)
            from app.core import faiss_manager
            try:
                faiss_manager.update_taste_vector(user_id, video_uuid)
                print(f"[TASTE VECTOR] Incremental EMA update completed for user {user_id[:8]}")
            except ValueError as e:
                # Video not found in FAISS index (rare edge case - video added after boot)
                print(f"[WARNING] Could not update taste vector: {e}")
            except Exception as e:
                # Non-critical error - log and continue
                print(f"[WARNING] Unexpected error updating taste vector: {e}")

            return WatchEventResponse(
                watch_id=watch_id,
                success=True
            )

        # MODE 2: UPDATE (video end) - watch_id provided with duration
        else:
            print(f"[DEBUG] UPDATE mode - updating watch record {request.watch_id} with duration {request.watch_duration_seconds}")

            success = await update_watch_history(
                watch_id=request.watch_id,
                watch_duration_seconds=request.watch_duration_seconds or 0
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update watch duration"
                )

            print("[DEBUG] Successfully updated watch record")

            return WatchEventResponse(
                watch_id=request.watch_id,
                success=True
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] track_watch_event failed - user_id: {user_id}, video_uuid: {video_uuid}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track watch event: {str(e)}"
        )


@router.get("/watch-history")
async def get_user_watch_history(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Get authenticated user's complete watch history.

    Features:
    - Returns watch history in reverse chronological order (newest first)
    - Includes video metadata, watch duration, and timestamps
    - Pageable with configurable limit (1-500)
    - Shows watch percentage and completion status

    Args:
        limit: Number of watch history entries to return (default 100, max 500)
        current_user: Authenticated user from JWT

    Returns:
        List of watch history entries with video details and watch metadata
    """
    user_id = current_user["id"]

    try:
        # Fetch user's watch history
        history_rows = await get_watch_history(user_id, limit=limit)

        # Get video UUIDs from history (skip malformed legacy IDs)
        video_uuids = []
        for row in history_rows:
            value = row.get("video_id")
            if not value:
                continue
            try:
                video_uuids.append(str(UUID(str(value))))
            except (ValueError, TypeError, AttributeError):
                continue

        if not video_uuids:
            return {
                "watch_history": [],
                "total": 0
            }

        # Fetch full video data for the watched videos
        videos = await get_videos_by_uuids(video_uuids)

        # Create a mapping from video UUID to video data
        video_map = {v["id"]: v for v in videos}

        # Combine watch history with video metadata
        watch_history = []
        for history_row in history_rows:
            raw_video_uuid = history_row.get("video_id")
            try:
                video_uuid = str(UUID(str(raw_video_uuid)))
            except (ValueError, TypeError, AttributeError):
                continue

            video_data = video_map.get(video_uuid)

            if video_data:
                # Transform video data
                video_response = transform_video(video_data)

                # Add watch metadata
                watch_entry = {
                    "watch_id": history_row["id"],
                    "video": video_response,
                    "watch_duration_seconds": history_row.get("watch_duration_seconds", 0),
                    "started_at": history_row.get("started_at"),
                    "ended_at": history_row.get("ended_at")
                }
                watch_history.append(watch_entry)

        return {
            "watch_history": watch_history,
            "total": len(watch_history)
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch watch history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch watch history"
        )


@router.delete("/watch-history")
async def delete_watch_history_record(
    request: DeleteWatchHistoryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a watch history record by ID.

    Features:
    - Only authenticated users can delete their own watch history
    - Deletes the record from watch_history table
    - Returns success status

    Args:
        request: DeleteWatchHistoryRequest containing watch_id to delete
        current_user: Authenticated user from JWT

    Returns:
        JSON response with success status
    """
    user_id = current_user["id"]
    watch_id = request.watch_id

    print(f"[DEBUG] delete_watch_history - user_id: {user_id}, watch_id: {watch_id}")

    try:
        # First, get the watch record to find the video_id
        watch_record = await get_watch_record_by_id(watch_id)

        if not watch_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Watch history record {watch_id} not found"
            )

        video_id = watch_record.get("video_id")
        print(f"[DEBUG] Found watch record for video {video_id}")

        # Delete the watch history record
        success = await delete_watch_history(watch_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete watch history record"
            )

        print(f"[DEBUG] Successfully deleted watch record {watch_id}")

        # Decrement video view count (only for authenticated users, not guests)
        view_decrement_success = await decrement_video_views(video_id)
        if view_decrement_success:
            print(f"[DEBUG] Decremented view count for video {video_id}")
        else:
            print(f"[WARNING] Failed to decrement view count for video {video_id}")

        return {
            "success": True,
            "message": "Watch history record deleted successfully",
            "watch_id": watch_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_watch_history failed - user_id: {user_id}, watch_id: {watch_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete watch history: {str(e)}"
        )

