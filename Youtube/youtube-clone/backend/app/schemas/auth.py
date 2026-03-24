from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    """User profile response."""
    user_id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    region: Optional[str] = None
    created_at: datetime


class UserPreferences(BaseModel):
    """User preferences."""
    theme: str = "dark"
    autoplay: bool = True
    restricted_mode: bool = False
    interaction_count: int = 0
    recommendation_phase: str = "cold_start"


class UpdateProfileRequest(BaseModel):
    """Request to update profile."""
    display_name: Optional[str] = None
    region: Optional[str] = None
    language: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    """Request to update preferences."""
    theme: Optional[str] = None
    autoplay: Optional[bool] = None
    restricted_mode: Optional[bool] = None


class GuestSessionRequest(BaseModel):
    """Request to create guest session."""
    guest_uuid: str
    region: Optional[str] = None
    language: Optional[str] = None
    device_type: Optional[str] = None


class GuestSessionResponse(BaseModel):
    """Guest session response."""
    guest_uuid: str
    interaction_count: int = 0
    created_at: datetime


class MigrateGuestRequest(BaseModel):
    """Request to migrate guest data to user account."""
    guest_uuid: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True
