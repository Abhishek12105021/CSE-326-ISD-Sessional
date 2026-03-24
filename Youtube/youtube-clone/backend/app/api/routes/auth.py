from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from app.schemas.auth import (
    UserProfile,
    UserPreferences,
    UpdateProfileRequest,
    UpdatePreferencesRequest,
    MigrateGuestRequest,
    MessageResponse
)
from app.core.supabase import get_supabase_admin
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user's profile.
    Token is verified by Supabase - this just fetches the profile data.
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
    """Update current user's profile."""
    supabase = get_supabase_admin()

    update_data = {k: v for k, v in request.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("users").update(update_data).eq(
        "id", current_user["id"]
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

    updated = result.data[0]
    return UserProfile(
        user_id=updated["id"],
        email=updated["email"],
        display_name=updated.get("display_name"),
        avatar_url=updated.get("avatar_url"),
        region=updated.get("region"),
        created_at=updated["created_at"]
    )


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get current user's preferences."""
    supabase = get_supabase_admin()

    result = supabase.table("user_preferences").select("*").eq(
        "user_id", current_user["id"]
    ).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found"
        )

    return UserPreferences(**result.data)


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's preferences."""
    supabase = get_supabase_admin()

    update_data = {k: v for k, v in request.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("user_preferences").update(update_data).eq(
        "user_id", current_user["id"]
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

    return UserPreferences(**result.data[0])


@router.post("/migrate-guest", response_model=MessageResponse)
async def migrate_guest_data(
    request: MigrateGuestRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Migrate guest session data to authenticated user.
    Call this after a guest user signs up to preserve their history.
    """
    supabase = get_supabase_admin()

    # Check if guest session exists
    guest_result = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", request.guest_uuid
    ).execute()

    if not guest_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    guest_session = guest_result.data[0]

    if guest_session.get("converted_to_user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest session already migrated"
        )

    # Call migration function
    try:
        result = supabase.rpc(
            "migrate_guest_to_user",
            {"p_guest_uuid": request.guest_uuid, "p_user_id": current_user["id"]}
        ).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {str(e)}"
        )

    return MessageResponse(
        message=f"Successfully migrated guest data to user {current_user['id']}",
        success=True
    )


@router.post("/logout", response_model=MessageResponse)
async def logout_current_session(current_user: dict = Depends(get_current_user)):
    """
    Logout current session.
    Note: Actual session invalidation is handled by Supabase on the frontend.
    This endpoint can be used for logging/analytics.
    """
    supabase = get_supabase_admin()

    # Update last login timestamp
    supabase.table("users").update({
        "last_login_at": datetime.utcnow().isoformat()
    }).eq("id", current_user["id"]).execute()

    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    Logout all sessions for the current user.
    Note: This signals intent - frontend should call supabase.auth.signOut({ scope: 'global' })
    """
    return MessageResponse(
        message="All sessions marked for logout. Frontend should call supabase.auth.signOut({ scope: 'global' })"
    )
