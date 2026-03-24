from fastapi import APIRouter, HTTPException, status
from datetime import datetime
from app.schemas.auth import (
    GuestSessionRequest,
    GuestSessionResponse,
    MessageResponse
)
from app.core.supabase import get_supabase_admin

router = APIRouter()


@router.post("/session", response_model=GuestSessionResponse)
async def create_guest_session(request: GuestSessionRequest):
    """
    Create or update a guest session.
    Called when an unauthenticated user visits the site.
    """
    supabase = get_supabase_admin()

    # Check if guest session already exists
    existing = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", request.guest_uuid
    ).execute()

    if existing.data:
        # Update existing session
        result = supabase.table("guest_sessions").update({
            "last_active_at": datetime.utcnow().isoformat(),
            "region": request.region or existing.data[0].get("region"),
            "device_type": request.device_type or existing.data[0].get("device_type"),
        }).eq("guest_uuid", request.guest_uuid).execute()

        session = result.data[0]
    else:
        # Create new session
        result = supabase.table("guest_sessions").insert({
            "guest_uuid": request.guest_uuid,
            "region": request.region,
            "language": request.language or "en",
            "device_type": request.device_type,
        }).execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create guest session"
            )

        session = result.data[0]

    return GuestSessionResponse(
        guest_uuid=session["guest_uuid"],
        interaction_count=session.get("interaction_count", 0),
        created_at=session["created_at"]
    )


@router.get("/session/{guest_uuid}", response_model=GuestSessionResponse)
async def get_guest_session(guest_uuid: str):
    """Get guest session info."""
    supabase = get_supabase_admin()

    result = supabase.table("guest_sessions").select("*").eq(
        "guest_uuid", guest_uuid
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found"
        )

    session = result.data[0]

    return GuestSessionResponse(
        guest_uuid=session["guest_uuid"],
        interaction_count=session.get("interaction_count", 0),
        created_at=session["created_at"]
    )


@router.delete("/session/{guest_uuid}", response_model=MessageResponse)
async def delete_guest_session(guest_uuid: str):
    """
    Delete guest session and all associated data.
    Use when user explicitly clears data or after migration.
    """
    supabase = get_supabase_admin()

    # Delete interactions
    supabase.table("interactions").delete().eq("guest_uuid", guest_uuid).execute()

    # Delete watch history
    supabase.table("watch_history").delete().eq("guest_uuid", guest_uuid).execute()

    # Delete guest session
    supabase.table("guest_sessions").delete().eq("guest_uuid", guest_uuid).execute()

    return MessageResponse(message="Guest session deleted successfully")
