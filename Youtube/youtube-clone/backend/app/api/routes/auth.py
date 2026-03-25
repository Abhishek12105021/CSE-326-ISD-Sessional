from fastapi import APIRouter, Depends
from app.schemas.auth import (
    UserProfile,
    UpdateProfileRequest,
    MigrateGuestRequest,
    MessageResponse
)
from app.api.deps import get_current_user

# /api/auth/*

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile.
    User data is extracted from the verified JWT token.
    """
    return UserProfile(
        user_id=current_user["id"],
        email=current_user["email"],
        display_name=current_user.get("display_name"),
        avatar_url=current_user.get("avatar_url"),
        region=current_user.get("region"),
        created_at=current_user["created_at"]
    )


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update current user's profile.
    Note: Profile updates (like region) are stored in localStorage on frontend.
    This endpoint acknowledges the update request.
    """
    # Merge update request with current user data
    return UserProfile(
        user_id=current_user["id"],
        email=current_user["email"],
        display_name=request.display_name if request.display_name else current_user.get("display_name"),
        avatar_url=current_user.get("avatar_url"),
        region=request.region if request.region else current_user.get("region"),
        created_at=current_user["created_at"]
    )


@router.post("/migrate-guest", response_model=MessageResponse)
async def migrate_guest_data(
    request: MigrateGuestRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Migrate guest session data to authenticated user.
    Note: Guest data is managed in localStorage on the frontend.
    This endpoint acknowledges the migration request.
    """
    return MessageResponse(
        message=f"Guest data migration acknowledged for user {current_user['id']}",
        success=True
    )


@router.post("/logout", response_model=MessageResponse)
async def logout_current_session(current_user: dict = Depends(get_current_user)):
    """
    Logout current session.
    Note: Actual session invalidation is handled by Supabase on the frontend.
    """
    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    Logout all sessions for the current user.
    Note: Frontend should call supabase.auth.signOut({ scope: 'global' })
    """
    return MessageResponse(
        message="All sessions marked for logout. Frontend should call supabase.auth.signOut({ scope: 'global' })"
    )
