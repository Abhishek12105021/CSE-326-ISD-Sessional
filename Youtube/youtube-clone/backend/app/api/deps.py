from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
from app.config import get_settings
from app.core.supabase import get_supabase_admin

settings = get_settings()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def verify_supabase_token(token: str) -> dict:
    """
    Verify a Supabase-issued JWT token.
    Returns the decoded payload if valid.
    """
    try:
        # Supabase uses HS256 with the JWT secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get current authenticated user.
    Verifies Supabase JWT and fetches user profile.
    """
    payload = verify_supabase_token(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user profile from database
    supabase = get_supabase_admin()
    result = supabase.table("users").select("*").eq("id", user_id).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return result.data


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
) -> Optional[dict]:
    """
    Dependency to optionally get current user.
    Returns None for unauthenticated requests (guest access).
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
