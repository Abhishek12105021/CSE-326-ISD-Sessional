from fastapi import APIRouter, Query
from datetime import datetime
import time
from app.schemas.auth import (
    GuestSessionRequest,
    GuestSessionResponse,
    MessageResponse
)
from app.schemas.feed import (
    GuestFeedRequest,
    GuestReloadFeedRequest,
    FeedResponse,
    VideoResponse,
    ChannelInfo,
    WatchEventRequest,
    WatchEventResponse,
    CategoriesResponse
)
from app.core.recommendation import (
    generate_phase1_feed,
    generate_phase2_feed,
    generate_phase3_feed
)
from app.core import faiss_manager
from app.db import insert_watch_history, update_watch_history, get_unique_categories, increment_video_views, get_videos_metadata_by_uuids
from app.utils.formatters import format_views, format_timestamp, generate_channel_avatar, is_verified
import numpy as np



# /api/guest/*
# NOTE: Guest sessions are now managed via localStorage on the frontend.
# These endpoints are kept for API compatibility but don't persist to database.

router = APIRouter()


@router.post("/session", response_model=GuestSessionResponse)
async def create_guest_session(request: GuestSessionRequest):
    """
    Acknowledge guest session creation.
    Guest data is managed via localStorage on the frontend.
    """
    return GuestSessionResponse(
        guest_uuid=request.guest_uuid,
        interaction_count=0,
        created_at=datetime.utcnow()
    )




@router.post("/feed", response_model=FeedResponse)
async def get_guest_feed(request: GuestFeedRequest):
    """
    Guest feed generation endpoint with FAISS-accelerated personalization.

    Receives watch history (UUIDs) from frontend localStorage.

    Flow:
    1. Parse request DTO (guest_uuid, region, watched_video_ids)
    2. Count interactions
    3. Determine phase
    4. If phase > 1: build weighted taste vector from FAISS embeddings
    5. Generate feed with interaction-count-aware strategy
    6. Transform and return

    Personalization improves as watch history grows:
    - Phase 1 (0): 50/50 global/local trending
    - Phase 2 (1-4): 20-40% semantic search based on count
    - Phase 3 (5+): 60-75% semantic same-region based on count
    """
    total_start = time.time()
    watched_uuids = request.watched_video_ids
    interaction_count = len(watched_uuids)

    print(f"\n{'#'*70}")
    print(f"[GUEST FEED] Starting for guest, region={request.region}, interactions={interaction_count}")
    print(f"{'#'*70}")

    # Build taste vector from FAISS embeddings (guests always rebuild, no caching)
    taste = None
    if interaction_count > 0:
        step_start = time.time()
        print(f"[GUEST FEED Step 1/3] Building taste vector from {interaction_count} watched videos...")

        # Get embeddings from FAISS manager's in-memory dict
        vectors = []
        for video_id in watched_uuids:
            embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)
            if embedding is not None:
                vectors.append(embedding)

        if vectors:
            # Simple weighted average (guests don't have timestamps for recency)
            vectors_arr = np.array(vectors, dtype=np.float32)
            taste = np.mean(vectors_arr, axis=0).astype(np.float32)
            taste = taste / (np.linalg.norm(taste) + 1e-10)  # Normalize

        step_elapsed = (time.time() - step_start) * 1000
        print(f"[GUEST FEED Step 1/3] Built taste vector: shape={taste.shape if taste is not None else None} ({step_elapsed:.1f}ms)")

    # Determine phase and generate feed
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print(f"[GUEST FEED Step 2/3] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(request.region, watched_uuids, request.limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print(f"[GUEST FEED Step 2/3] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, request.region, watched_uuids, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, watched_uuids, request.limit)

    else:
        strategy = "phase_3_personalized"
        print(f"[GUEST FEED Step 2/3] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, request.region, watched_uuids, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, watched_uuids, request.limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST FEED Step 2/3] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Fetch metadata
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST FEED Step 3/3] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform
    def transform_video(v: dict) -> VideoResponse:
        return VideoResponse(
            id=v["id"],
            video_id=v["video_id"],
            title=v["title"],
            thumbnail=v["thumbnail_link"],
            channel=ChannelInfo(
                name=v["channel_title"],
                avatar=generate_channel_avatar(v["channel_title"]),
                verified=is_verified(v.get("views", 0), v.get("likes", 0)),
                id=v["channel_title"]
            ),
            views=format_views(v.get("views", 0)),
            timestamp=format_timestamp(v.get("publish_time", "")),
            duration="10:00",
            category=v.get("category_name", "Unknown"),
            velocity_score=v.get("velocity_score")
        )

    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[GUEST FEED] Complete! Strategy: {strategy}, Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )




@router.post("/reload", response_model=FeedResponse)
async def reload_guest_feed(request: GuestReloadFeedRequest):
    """
    Guest lazy loading endpoint - reload feed with more videos excluding already-shown ones.

    This endpoint allows infinite scrolling by returning 30 new recommended videos
    that exclude all previously shown videos. It uses the same personalization logic
    as the /feed endpoint but filters out both watched videos AND excluded videos.

    Args:
        request: GuestReloadFeedRequest with:
          - guest_uuid: Guest identifier
          - region: User's region preference
          - watched_video_ids: All videos watched so far (for taste vector)
          - excluded_video_ids: All videos shown in current feed (to exclude)
          - limit: Number of new videos to return

    Returns:
        FeedResponse with 30 new videos, strategy, interaction count, and total
    """
    total_start = time.time()
    watched_uuids = request.watched_video_ids
    excluded_ids = request.excluded_video_ids or []
    interaction_count = len(watched_uuids)

    print(f"\n{'#'*70}")
    print(f"[GUEST RELOAD] Starting for guest, region={request.region}, "
          f"watching={interaction_count}, excluding={len(excluded_ids)}")
    print(f"{'#'*70}")

    # Merge watched + excluded for comprehensive filtering
    all_excluded = list(set(watched_uuids + excluded_ids))

    # Build taste vector from FAISS embeddings (same as /feed)
    taste = None
    if interaction_count > 0:
        step_start = time.time()
        print(f"[GUEST RELOAD Step 1/3] Building taste vector from {interaction_count} watched videos...")

        vectors = []
        for video_id in watched_uuids:
            embedding = faiss_manager.UUID_TO_EMBEDDING.get(video_id)
            if embedding is not None:
                vectors.append(embedding)

        if vectors:
            vectors_arr = np.array(vectors, dtype=np.float32)
            taste = np.mean(vectors_arr, axis=0).astype(np.float32)
            taste = taste / (np.linalg.norm(taste) + 1e-10)

        step_elapsed = (time.time() - step_start) * 1000
        print(f"[GUEST RELOAD Step 1/3] Built taste vector ({step_elapsed:.1f}ms)")

    # Determine phase and generate feed (with all_excluded filter)
    step_start = time.time()
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        print(f"[GUEST RELOAD Step 2/3] Phase 1 (Cold Start): Generating trending feed...")
        video_uuids = await generate_phase1_feed(request.region, all_excluded, request.limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        print(f"[GUEST RELOAD Step 2/3] Phase 2 (Warm-Up): Generating mixed feed...")
        video_uuids = await generate_phase2_feed(
            taste, request.region, all_excluded, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, all_excluded, request.limit)

    else:
        strategy = "phase_3_personalized"
        print(f"[GUEST RELOAD Step 2/3] Phase 3 (Personalized): Generating semantic feed...")
        video_uuids = await generate_phase3_feed(
            taste, request.region, all_excluded, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, all_excluded, request.limit)

    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST RELOAD Step 2/3] Generated {len(video_uuids)} video UUIDs using {strategy} ({step_elapsed:.1f}ms)")

    # Fetch metadata
    step_start = time.time()
    videos = await get_videos_metadata_by_uuids(video_uuids)
    step_elapsed = (time.time() - step_start) * 1000
    print(f"[GUEST RELOAD Step 3/3] Fetched metadata for {len(videos)} videos ({step_elapsed:.1f}ms)")

    # Transform
    def transform_video(v: dict) -> VideoResponse:
        return VideoResponse(
            id=v["id"],
            video_id=v["video_id"],
            title=v["title"],
            thumbnail=v["thumbnail_link"],
            channel=ChannelInfo(
                name=v["channel_title"],
                avatar=generate_channel_avatar(v["channel_title"]),
                verified=is_verified(v.get("views", 0), v.get("likes", 0)),
                id=v["channel_title"]
            ),
            views=format_views(v.get("views", 0)),
            timestamp=format_timestamp(v.get("publish_time", "")),
            duration="10:00",
            category=v.get("category_name", "Unknown"),
            velocity_score=v.get("velocity_score")
        )

    video_responses = [transform_video(v) for v in videos]

    total_elapsed = (time.time() - total_start) * 1000
    print(f"{'#'*70}")
    print(f"[GUEST RELOAD] Complete! Strategy: {strategy}, Videos: {len(video_responses)}, Total: {total_elapsed:.1f}ms")
    print(f"{'#'*70}\n")

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )


@router.post("/watch", response_model=WatchEventResponse)
async def record_guest_watch(request: WatchEventRequest):
    """
    Record guest watch event (INSERT or UPDATE).

    Two modes:

    MODE 1 - INSERT (when user clicks video):
      Request: { video_uuid, guest_uuid }
      Backend: INSERT watch_history row with duration=0
      Response: { watch_id: "uuid-...", success: true }
      Frontend: Saves watch_id, launches iframe

    MODE 2 - UPDATE (when user leaves/navigates):
      Request: { video_uuid, watch_id, watch_duration_seconds, guest_uuid }
      Backend: UPDATE watch_history row with actual duration from YouTube API
      Response: { success: true }
      Frontend: Had obtained duration from YouTube iframe API before sending
    """
    # MODE 1: INSERT
    if not request.watch_id:
        watch_id = await insert_watch_history(
            user_id=None,
            guest_uuid=request.guest_uuid,
            video_uuid=request.video_uuid
        )

        # Increment video view count (guests can only increase, not decrease)
        view_increment_success = await increment_video_views(request.video_uuid)
        if view_increment_success:
            print(f"[DEBUG] Incremented view count for video {request.video_uuid} (guest)")
        else:
            print(f"[WARNING] Failed to increment view count for video {request.video_uuid} (guest)")

        return WatchEventResponse(watch_id=watch_id, success=True)

    # MODE 2: UPDATE
    else:
        await update_watch_history(
            watch_id=request.watch_id,
            watch_duration_seconds=request.watch_duration_seconds or 0,
            # video_duration_seconds=request.video_duration_seconds
        )
        return WatchEventResponse(watch_id=request.watch_id, success=True)


# @router.get("/session/{guest_uuid}", response_model=GuestSessionResponse)
# async def get_guest_session(guest_uuid: str):
#     """
#     Return guest session info.
#     Guest data is managed via localStorage on the frontend.
#     """
#     return GuestSessionResponse(
#         guest_uuid=guest_uuid,
#         interaction_count=0,
#         created_at=datetime.utcnow()
#     )


# @router.delete("/session/{guest_uuid}", response_model=MessageResponse)
# async def delete_guest_session(guest_uuid: str):
#     """
#     Acknowledge guest session deletion.
#     Actual deletion happens via localStorage on the frontend.
#     """
#     return MessageResponse(message="Guest session deleted successfully")
