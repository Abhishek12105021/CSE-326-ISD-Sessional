from pydantic import BaseModel
from typing import Optional


class ChannelInfo(BaseModel):
    name: str
    avatar: str
    verified: bool
    id: str


class VideoResponse(BaseModel):
    id: str  # UUID from videos.id
    video_id: str  # YouTube ID
    title: str
    thumbnail: str
    channel: ChannelInfo
    views: str
    timestamp: str
    duration: str
    category: str
    velocity_score: Optional[float] = None


class FeedResponse(BaseModel):
    videos: list[VideoResponse]
    strategy: str
    interaction_count: int
    total: int


class GuestFeedRequest(BaseModel):
    """DTO for guest feed generation"""
    guest_uuid: str
    region: str = "US"
    limit: int = 30
    watched_video_ids: list[str] = []  # UUIDs from videos.id


class WatchEventRequest(BaseModel):
    """DTO for watch event tracking"""
    video_uuid: str  # UUID from videos.id
    watch_id: Optional[str] = None  # present only on UPDATE call
    watch_duration_seconds: Optional[int] = None  # from YouTube iframe API, only on UPDATE
    guest_uuid: Optional[str] = None  # for guests


class WatchEventResponse(BaseModel):
    watch_id: Optional[str] = None  # only returned on INSERT
    success: bool = True


class CategoriesResponse(BaseModel):
    categories: list[str]
