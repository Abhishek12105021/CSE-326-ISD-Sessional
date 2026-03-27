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


class DeleteWatchHistoryRequest(BaseModel):
    """Request to delete a watch history record"""
    watch_id: str  # ID of the watch history record to delete


class CategoriesResponse(BaseModel):
    categories: list[str]


# ======================== VIDEO METADATA ========================

class VideoMetadataRequest(BaseModel):
    """Request to get complete video metadata by UUID"""
    video_uuid: str  # UUID from videos.id
    
class VideoMetadataResponse(BaseModel):
    """Complete video metadata response with all available information"""
    id: str  # UUID from videos.id
    video_id: str  # YouTube ID
    title: str
    description: str
    thumbnail: str
    channel: ChannelInfo
    views: str  # Formatted (e.g., "1.2M views")
    views_raw: int  # Raw number
    likes: int
    dislikes: int
    timestamp: str  # Formatted (e.g., "2 days ago")
    publish_time_raw: str  # ISO timestamp
    duration: str
    category: str
    velocity_score: Optional[float] = None
    region: str
    tags: list[str] = []
    has_embedding: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ======================== LIKES ========================


class LikeVideoRequest(BaseModel):
    """Request to like/unlike a video"""
    video_uuid: str  # UUID from videos.id


class LikeResponse(BaseModel):
    """Response after like/unlike action"""
    success: bool
    message: str
    is_liked: bool  # current state after action


class LikesListResponse(BaseModel):
    """Response containing user's liked videos"""
    videos: list[VideoResponse]
    total: int


# ======================== DISLIKES ========================


class DislikeVideoRequest(BaseModel):
    """Request to dislike/remove dislike from a video"""
    video_uuid: str  # UUID from videos.id


class DislikeResponse(BaseModel):
    """Response after dislike/remove dislike action"""
    success: bool
    message: str
    is_disliked: bool  # current state after action


class DislikesListResponse(BaseModel):
    """Response containing user's disliked videos"""
    videos: list[VideoResponse]
    total: int


# ======================== SUBSCRIPTIONS ========================


class SubscribeRequest(BaseModel):
    """Request to subscribe/unsubscribe from a channel"""
    channel_name: str  # Channel title from videos.channel_title


class SubscriptionResponse(BaseModel):
    """Response after subscribe/unsubscribe action"""
    success: bool
    message: str
    is_subscribed: bool  # current subscription state after action


class SubscribedChannelsResponse(BaseModel):
    """Response containing user's subscribed channels"""
    channels: list[str]
    total: int


class AllChannelsResponse(BaseModel):
    """Response containing all available channels"""
    channels: list[str]
    total: int


# ======================== RELOAD FEED (LAZY LOADING) ========================


class ReloadFeedRequest(BaseModel):
    """Request to reload feed with lazy loading (authenticated users)"""
    excluded_video_ids: list[str] = []  # UUIDs of videos already shown
    limit: int = 30  # Number of new videos to return


class GuestReloadFeedRequest(BaseModel):
    """Request to reload feed with lazy loading (guest users)"""
    guest_uuid: str
    region: str = "US"
    watched_video_ids: list[str] = []  # All videos watched so far (including current feed)
    excluded_video_ids: list[str] = []  # Videos already shown in current feed
    limit: int = 30  # Number of new videos to return


# ======================== RELOAD SEARCH (LAZY LOADING) ========================


class SearchReloadRequest(BaseModel):
    """Request to reload search results with lazy loading"""
    q: str  # Original search query
    excluded_video_ids: list[str] = []  # UUIDs of videos already shown
    offset: int = 0  # Pagination offset for next batch
    limit: int = 25  # Number of new videos to return (20-30)


class ReloadRecommendRequest(BaseModel):
    """Request to reload recommendations with lazy loading"""
    video_id: str  # Reference video UUID
    excluded_video_ids: list[str] = []  # UUIDs of recommendations already shown
    limit: int = 15  # Number of new recommendations to return