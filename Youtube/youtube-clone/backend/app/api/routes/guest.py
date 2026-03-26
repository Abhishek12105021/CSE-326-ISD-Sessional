from fastapi import APIRouter
from datetime import datetime
from app.schemas.auth import (
    GuestSessionRequest,
    GuestSessionResponse,
    MessageResponse
)
from app.schemas.feed import (
    GuestFeedRequest,
    FeedResponse,
    VideoResponse,
    ChannelInfo,
    WatchEventRequest,
    WatchEventResponse,
    CategoriesResponse
)
from app.core.recommendation import (
    build_taste_vector_from_uuids,
    generate_phase1_feed,
    generate_phase2_feed,
    generate_phase3_feed
)
from app.db import insert_watch_history, update_watch_history, get_unique_categories
from app.utils.formatters import format_views, format_timestamp, generate_channel_avatar, is_verified



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
    Guest feed generation endpoint with adaptive personalization.

    Receives watch history (UUIDs) from frontend localStorage.

    Flow:
    1. Parse request DTO (guest_uuid, region, watched_video_ids)
    2. Count interactions
    3. Determine phase
    4. If phase > 1: build weighted taste vector from UUIDs
    5. Generate feed with interaction-count-aware strategy
    6. Transform and return

    Personalization improves as watch history grows:
    - Phase 1 (0): 50/50 global/local trending
    - Phase 2 (1-4): 20-40% semantic search based on count
    - Phase 3 (5+): 60-75% semantic same-region based on count
    """

    watched_uuids = request.watched_video_ids

    interaction_count = len(watched_uuids)

    # Determine phase
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        videos = await generate_phase1_feed(request.region, request.limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        # Build taste vector with recency weighting (for guest, use linear decay)
        taste = await build_taste_vector_from_uuids(
            watched_uuids,
            watch_history=None,  # Guests don't have detailed history
            use_recency_weighting=True
        )
        videos = await generate_phase2_feed(
            taste, request.region, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, request.limit)

    else:
        strategy = "phase_3_personalized"
        # Build taste vector with recency weighting
        taste = await build_taste_vector_from_uuids(
            watched_uuids,
            watch_history=None,
            use_recency_weighting=True
        )
        videos = await generate_phase3_feed(
            taste, request.region, interaction_count, request.limit
        ) if taste is not None else await generate_phase1_feed(request.region, request.limit)

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
        return WatchEventResponse(watch_id=watch_id, success=True)

    # MODE 2: UPDATE
    else:
        await update_watch_history(
            watch_id=request.watch_id,
            watch_duration_seconds=request.watch_duration_seconds or 0
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
