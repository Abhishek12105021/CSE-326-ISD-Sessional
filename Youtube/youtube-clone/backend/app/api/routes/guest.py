from fastapi import APIRouter
from datetime import datetime
from app.schemas.auth import (
    GuestSessionRequest,
    GuestSessionResponse,
    MessageResponse
)


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


@router.get("/session/{guest_uuid}", response_model=GuestSessionResponse)
async def get_guest_session(guest_uuid: str):
    """
    Return guest session info.
    Guest data is managed via localStorage on the frontend.
    """
    return GuestSessionResponse(
        guest_uuid=guest_uuid,
        interaction_count=0,
        created_at=datetime.utcnow()
    )


# @router.delete("/session/{guest_uuid}", response_model=MessageResponse)
# async def delete_guest_session(guest_uuid: str):
#     """
#     Acknowledge guest session deletion.
#     Actual deletion happens via localStorage on the frontend.
#     """
#     return MessageResponse(message="Guest session deleted successfully")
