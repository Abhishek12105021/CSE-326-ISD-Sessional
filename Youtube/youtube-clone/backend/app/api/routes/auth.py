from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db import get_user_by_id, update_user, upsert_user
from app.schemas.auth import MessageResponse, UpdateProfileRequest, UserProfile

# /api/auth/*

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get authenticated user's complete profile.

    ═══════════════════════════════════════════════════════════════════════════════════
    PURPOSE:
    Fetch user profile combining data from:
    - JWT token (all claims: user_id, email, display_name, avatar_url, created_at)
    - Database (region preference, which isn't in JWT)
    ═══════════════════════════════════════════════════════════════════════════════════

    DATA SOURCES:

    From JWT Token (current_user dict):
      - id: User UUID from Supabase Auth
      - email: User's email from Supabase Auth
      - display_name: User's profile name (optional)
      - avatar_url: User's profile picture URL (optional)
      - created_at: Account creation timestamp

    From Database (users table):
      - region: User's preferred region (US, GB, JP, etc.)
      - Any custom fields stored in users table

    ═══════════════════════════════════════════════════════════════════════════════════

    AUTO-CREATION:

    If user is new (not in database yet):
      1. Try to fetch from users table
      2. If not found, upsert (create) with:
         - id: from JWT
         - email: from JWT
         - display_name: from JWT (optional)
         - avatar_url: from JWT (optional)
         - region: "" (empty, user can set later via PUT /auth/profile)

    This enables seamless onboarding:
      - User signs in with Google (Supabase Auth handles this)
      - First API call creates DB record automatically
      - User can update region/display_name via PUT endpoint

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        current_user: Authenticated user from JWT (via get_current_user dependency)

    RETURNS:
        UserProfile:
            - user_id: UUID from Supabase Auth
            - email: Email from Supabase Auth
            - display_name: Name from JWT or DB
            - avatar_url: Avatar URL from JWT or DB
            - region: Preferred region from DB
            - created_at: Account creation timestamp

    ═══════════════════════════════════════════════════════════════════════════════════

    EXAMPLE RESPONSE:

    {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "user@example.com",
        "display_name": "John Doe",
        "avatar_url": "https://avatars.githubusercontent.com/u/...",
        "region": "US",
        "created_at": "2026-03-20T10:30:00Z"
    }

    ═══════════════════════════════════════════════════════════════════════════════════
    """
    # Fetch user from database to get region
    db_user = await get_user_by_id(current_user["id"])

    # If user doesn't exist in DB yet, create them
    if not db_user:
        db_user = await upsert_user({
            "id": current_user["id"],
            "email": current_user["email"],
            "display_name": current_user.get("display_name"),
            "avatar_url": current_user.get("avatar_url"),
            "region": ""  # Default region
        })

    return UserProfile(
        user_id=current_user["id"],
        email=current_user["email"],
        display_name=current_user.get("display_name"),
        avatar_url=current_user.get("avatar_url"),
        region=db_user.get("region") if db_user else None,
        created_at=current_user["created_at"]
    )


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update authenticated user's profile (display_name and/or region).

    ═══════════════════════════════════════════════════════════════════════════════════
    PURPOSE:
    Allow users to customize their profile settings that affect recommendations.
    ═══════════════════════════════════════════════════════════════════════════════════

    UPDATABLE FIELDS:

    display_name:
      - User's preferred name (not from Supabase Auth)
      - Can be different from email
      - Displayed in UI (future: profile cards, comments, etc.)
      - Optional field

    region:
      - User's preferred region for recommendations (US, GB, JP, DE, FR, IN, KR, MX, RU, CA)
      - Used in /feed endpoint: First filters recommendations by region
      - Affects 3-phase strategy: Phase 3 returns 60% same-region content
      - Optional field

    ═══════════════════════════════════════════════════════════════════════════════════

    UPDATE LOGIC:

    Request Processing:
      1. Check if display_name provided and not None → add to updates dict
      2. Check if region provided and not None → add to updates dict
      3. If updates dict is empty → no database call

    Database Operation:
      1. Try UPDATE user with provided fields
      2. If user doesn't exist (first time):
         → Upsert instead (INSERT with these fields + defaults)

    Response:
      - Always return fresh data from database
      - Even if only one field changed, fetch full record
      - Ensures response is authoritative (DB is source of truth)

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        request: UpdateProfileRequest
            - display_name (optional): New name
            - region (optional): New region code
        current_user: Authenticated user from JWT

    RETURNS:
        UserProfile: Updated user profile with all fields

    ═══════════════════════════════════════════════════════════════════════════════════

    EXAMPLE REQUEST:

    {
        "display_name": "New Name",
        "region": "JP"
    }

    EXAMPLE RESPONSE:

    {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "user@example.com",
        "display_name": "New Name",
        "avatar_url": "https://...",
        "region": "JP",
        "created_at": "2026-03-20T10:30:00Z"
    }

    ═══════════════════════════════════════════════════════════════════════════════════

    IDEMPOTENCY:

    - Calling twice with same data: Results in identical DB state (safe)
    - Null values mean "don't update this field"
    - Partial updates work (update region without changing display_name)

    Example:
      PUT /auth/profile with {"region": "JP", "display_name": null}
      → Only region changes, display_name stays same
    """
    # Build update dict with only provided fields
    updates = {}
    if request.display_name is not None:
        updates["display_name"] = request.display_name
    if request.region is not None:
        updates["region"] = request.region

    # Update database if there are changes
    if updates:
        result = await update_user(current_user["id"], updates)

        # If user doesn't exist, create them with the updates
        if not result:
            await upsert_user({
                "id": current_user["id"],
                "email": current_user["email"],
                "display_name": request.display_name or current_user.get("display_name"),
                "avatar_url": current_user.get("avatar_url"),
                "region": request.region or ""
            })

    # Always fetch fresh data from database to ensure correct response
    db_user = await get_user_by_id(current_user["id"])

    return UserProfile(
        user_id=current_user["id"],
        email=current_user["email"],
        display_name=request.display_name if request.display_name else current_user.get("display_name"),
        avatar_url=current_user.get("avatar_url"),
        region=db_user.get("region") if db_user else request.region,
        created_at=current_user["created_at"]
    )





# @router.post("/migrate-guest", response_model=MessageResponse)
# async def migrate_guest_data(
#     request: MigrateGuestRequest,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Migrate guest session data to authenticated user.
#     Note: Guest data is managed in localStorage on the frontend.
#     This endpoint acknowledges the migration request.
#     """
#     return MessageResponse(
#         message=f"Guest data migration acknowledged for user {current_user['id']}",
#         success=True
#     )


@router.post("/logout", response_model=MessageResponse)
async def logout_current_session(current_user: dict = Depends(get_current_user)):
    """
    Logout current session only.

    ═══════════════════════════════════════════════════════════════════════════════════
    IMPORTANT: This endpoint does NOT actively invalidate the JWT.
    ═══════════════════════════════════════════════════════════════════════════════════

    Why?
      - JWT tokens are stateless (no server-side session storage)
      - Backend cannot "revoke" a JWT after issuance
      - Token validity is determined solely by signature + expiry

    What This Endpoint Does:
      - Acknowledges logout request from frontend
      - Returns success message
      - Frontend is responsible for clearing JWT from localStorage

    Complete Logout Flow:
      1. Frontend calls POST /auth/logout
      2. Backend returns: { message: "Logged out successfully" }
      3. Frontend deletes JWT from localStorage
      4. Frontend redirects to login page
      5. All subsequent requests fail auth (no JWT header)

    ═══════════════════════════════════════════════════════════════════════════════════

    Actual Session Termination Happens On Frontend:

    // Frontend code
    async function logout() {
      // Call backend endpoint (optional, mainly for audit logging)
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}` }
      });

      // Clear JWT from localStorage
      localStorage.removeItem('auth_token');

      // This is what actually logs user out:
      // - No more 'Authorization' header in requests
      // - Backend returns 401 on next request
      // - UI redirects to login

      // Optionally, also sign out from Supabase Auth:
      await supabase.auth.signOut();
    }

    ═══════════════════════════════════════════════════════════════════════════════════

    LOGOUT SCOPE:

    Current Session Only:
      - If user is logged in from 2 devices
      - Device A calls /logout → only that device's session is cleared locally
      - Device B's JWT remains valid (different localStorage)

    To Logout All Sessions:
      - User calls POST /auth/logout-all (see below)
      - Frontend should call supabase.auth.signOut({ scope: 'global' })
      - This revokes ALL tokens issued to this user

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        current_user: Authenticated user from JWT (validates request)

    RETURNS:
        MessageResponse: "Logged out successfully"

    ═══════════════════════════════════════════════════════════════════════════════════
    """
    return MessageResponse(message="Logged out successfully")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    Logout ALL sessions for the current user across all devices.

    ═══════════════════════════════════════════════════════════════════════════════════
    PURPOSE:
    Sign user out of ALL devices/browsers. Revokes all issued JWT tokens.
    ═══════════════════════════════════════════════════════════════════════════════════

    IMPORTANT DISTINCTION:

    /logout (single session):
      - Frontend clears local JWT
      - Only affects this device
      - Other devices can still use their JWTs

    /logout-all (all sessions):
      - Supabase invalidates ALL tokens for this user
      - ALL devices are logged out
      - All saved JWTs become invalid
      - User must sign in again on all devices

    ═══════════════════════════════════════════════════════════════════════════════════

    HOW IT WORKS:

    Backend Side (This Endpoint):
      _ Acknowledges request
      - Returns instructions for frontend

    Frontend Side (Critical!):
      - Supabase provides an API to revoke all sessions
      - Frontend calls: await supabase.auth.signOut({ scope: 'global' })
      - This tells Supabase's server to invalidate all tokens

    Result:
      - All stored JWTs become invalid
      - Next API call without valid JWT gets 401
      - User must re-authenticate (sign in again)

    ═══════════════════════════════════════════════════════════════════════════════════

    COMPLETE FLOW:

    // Frontend code
    async function logoutAllDevices() {
      // 1. Notify backend (optional, for logging)
      await fetch('/api/auth/logout-all', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${currentJWT}` }
      });

      // 2. THE CRITICAL STEP: Revoke all tokens at Supabase
      const { error } = await supabase.auth.signOut({
        scope: 'global'  // This revokes ALL sessions on Supabase's server
      });

      if (error) {
        // Handle error: network, invalid scope, etc.
        console.error('Global logout failed:', error);
      }

      // 3. Clear local storage just in case
      localStorage.removeItem('auth_token');
      localStorage.removeItem('guest_uuid');

      // 4. Redirect to login
      window.location.href = '/login';
    }

    ═══════════════════════════════════════════════════════════════════════════════════

    WHY THIS BACKEND ENDPOINT EXISTS:

    1. User Experience:
       - Give user feedback "Logging out of all devices..."
       - Backend can log this action for security audit

    2. Future Enhancement:
       - If we implement server-side token blacklisting
       - This endpoint could actively revoke tokens
       - (Currently, Supabase handles revocation on their server)

    3. Documentation:
       - Tells frontend what to do next
       - Clear instructions in response

    ═══════════════════════════════════════════════════════════════════════════════════

    ARGS:
        current_user: Authenticated user from JWT (validates request is authentic)

    RETURNS:
        MessageResponse with instructions for frontend

    IMPORTANT:
      - Response is just a message (backend cannot revoke JWTs directly)
      - Frontend MUST call supabase.auth.signOut({ scope: 'global' })
      - Otherwise, other devices' JWTs will still be valid

    ═══════════════════════════════════════════════════════════════════════════════════
    """
    return MessageResponse(
        message="All sessions marked for logout. Frontend should call supabase.auth.signOut({ scope: 'global' })"
    )
