from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.api.deps import get_current_user
from app.schemas.feed import FeedResponse, VideoResponse, ChannelInfo, CategoriesResponse
from app.core.recommendation import (
    build_taste_vector_from_uuids,
    generate_phase1_feed,
    generate_phase2_feed,
    generate_phase3_feed
)
from app.db import get_watch_history, get_unique_categories
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
    region: str = Query(default="US"),
    limit: int = Query(default=30, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    Authenticated user feed endpoint.

    Flow:
    1. Extract user_id from JWT
    2. Query watch_history table
    3. Determine phase based on count
    4. Generate feed
    5. Transform and return
    """
    user_id = current_user["id"]

    # Fetch watch history (contains video UUIDs)
    history_rows = await get_watch_history(user_id, limit=50)
    watched_uuids = [row["video_id"] for row in history_rows]  # videos.id UUIDs

    interaction_count = len(watched_uuids)

    # Determine phase
    if interaction_count == 0:
        strategy = "phase_1_cold_start"
        videos = await generate_phase1_feed(region, limit)

    elif 1 <= interaction_count <= 4:
        strategy = "phase_2_warm_up"
        taste = await build_taste_vector_from_uuids(watched_uuids)
        videos = await generate_phase2_feed(taste, region, limit) if taste is not None else await generate_phase1_feed(region, limit)

    else:
        strategy = "phase_3_personalized"
        taste = await build_taste_vector_from_uuids(watched_uuids)
        videos = await generate_phase3_feed(taste, region, limit) if taste is not None else await generate_phase1_feed(region, limit)

    video_responses = [transform_video(v) for v in videos]

    return FeedResponse(
        videos=video_responses,
        strategy=strategy,
        interaction_count=interaction_count,
        total=len(video_responses)
    )


@router.get("/trending", response_model=FeedResponse)
async def get_trending_feed(
    region: Optional[str] = Query(default="US"),
    limit: int = Query(default=30, le=50)
):
    """Pure trending feed (no personalization)"""
    videos = await generate_phase1_feed(region, limit)
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
