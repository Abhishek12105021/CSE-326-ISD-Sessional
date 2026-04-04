from datetime import datetime
from functools import lru_cache
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.exceptions import JWKError, JWTError

from app.config import get_settings

settings = get_settings()
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_jwks():
    """
    Fetch and cache Supabase's JWKS (JSON Web Key Set).
    Used to verify ES256 signed JWTs.
    """
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    response = httpx.get(jwks_url)
    response.raise_for_status()
    return response.json()


def get_public_key(token: str):
    """
    Get the public key from JWKS that matches the token's kid.
    """
    # Get the key ID from token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg")

    jwks = get_jwks()

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return jwk.construct(key, alg)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find appropriate key",
    )


def verify_supabase_token(token: str) -> dict:
    """
    Verify a Supabase-issued JWT token.
    Supports both ES256 (asymmetric) and HS256 (symmetric) algorithms.
    Returns the decoded payload if valid.
    """
    try:
        # Get the algorithm from token header
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")

        if alg == "ES256":
            # Use JWKS public key for ES256
            public_key = get_public_key(token)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                audience="authenticated"
            )
        else:
            # Fallback to HS256 with JWT secret
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )

        return payload
    except (JWTError, JWKError) as e:
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
    Verifies Supabase JWT and returns user info from the token payload.
    """
    payload = verify_supabase_token(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Extract user data from JWT payload (no database call needed)
    user_metadata = payload.get("user_metadata", {})

    # Convert iat (issued at) Unix timestamp to datetime
    iat = payload.get("iat")
    created_at = datetime.fromtimestamp(iat) if iat else datetime.utcnow()

    return {
        "id": user_id,
        "email": payload.get("email"),
        "display_name": user_metadata.get("full_name") or user_metadata.get("name"),
        "avatar_url": user_metadata.get("avatar_url") or user_metadata.get("picture"),
        "created_at": created_at,
    }


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
