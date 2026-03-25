"""
Simple database client using httpx to call Supabase REST API directly.
This bypasses the supabase-py client which has httpx compatibility issues.
"""
import httpx
from typing import Optional
from app.config import get_settings

settings = get_settings()

# Supabase REST API base URL
REST_URL = f"{settings.supabase_url}/rest/v1"

# Headers for authenticated requests (using service role key for admin access)
HEADERS = {
    "apikey": settings.supabase_service_key,
    "Authorization": f"Bearer {settings.supabase_service_key}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


async def get_user_by_id(user_id: str) -> Optional[dict]:
    """
    Fetch user from Supabase users table by ID.

    SQL equivalent:
    SELECT * FROM users WHERE id = {user_id}
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REST_URL}/users",
            headers=HEADERS,
            params={"id": f"eq.{user_id}", "select": "*"}
        )

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]
        return None


async def update_user(user_id: str, updates: dict) -> Optional[dict]:
    """
    Update user in Supabase users table.

    SQL equivalent:
    UPDATE users SET {updates} WHERE id = {user_id}
    """
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{REST_URL}/users",
            headers=HEADERS,
            params={"id": f"eq.{user_id}"},
            json=updates
        )

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]
        return None


async def upsert_user(user_data: dict) -> Optional[dict]:
    """
    Insert or update user in Supabase users table.
    """
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{REST_URL}/users",
            headers=headers,
            json=user_data
        )

        if response.status_code in (200, 201):
            data = response.json()
            if data and len(data) > 0:
                return data[0]
        return None


# ==================== FEED GENERATION FUNCTIONS ====================


async def call_rpc(function_name: str, params: dict) -> list[dict]:
    """Generic RPC caller for Supabase functions"""
    rpc_url = f"{settings.supabase_url}/rest/v1/rpc/{function_name}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            rpc_url,
            headers=HEADERS,
            json=params
        )
        response.raise_for_status()
        return response.json()


async def search_videos_semantic(
    query_embedding: list[float],
    filter_country: Optional[str],
    match_count: int
) -> list[dict]:
    """
    Search videos by semantic similarity using SQL query via REST API.

    Fallback: Uses trending videos ordered by views.
    Full implementation would use pgvector with:
    SELECT * FROM videos
    WHERE country_code = {filter_country} (if provided)
    ORDER BY embedding <-> query_embedding
    LIMIT match_count
    """
    # Without pgvector RPC, return trending videos as fallback
    return await get_trending_videos(filter_country, match_count, 200, [])


async def get_trending_videos(
    filter_country: Optional[str],
    match_count: int,
    pool_size: int,
    exclude_ids: list[str]
) -> list[dict]:
    """
    Fetch trending videos using SQL query via REST API.

    SQL equivalent:
    SELECT * FROM videos
    WHERE country_code = {filter_country} (if provided)
    AND id NOT IN exclude_ids
    ORDER BY views DESC
    LIMIT match_count
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "select": "*",
            "order": "views.desc",  # SQL: ORDER BY views DESC
            "limit": pool_size
        }

        if filter_country:
            params["country_code"] = f"eq.{filter_country}"

        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params=params
        )
        response.raise_for_status()
        videos = response.json()

        # Filter out excluded videos (SQL: WHERE id NOT IN (...))
        filtered = [v for v in videos if v["id"] not in exclude_ids]

        # Return up to match_count videos
        return filtered[:match_count]


async def get_videos_by_uuids(uuids: list[str]) -> list[dict]:
    """
    Fetch video rows by UUID id values.
    Returns full rows including embeddings.

    Used when converting guest watch history (UUIDs) to video data.
    """
    if not uuids:
        return []

    import json

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={
                "select": "*",  # all columns including embedding
                "id": f"in.({','.join(uuids)})",
                "limit": len(uuids)
            }
        )
        response.raise_for_status()
        rows = response.json()

        # Parse embedding if it's a string (REST API serializes as JSON string)
        for row in rows:
            if row.get("embedding") and isinstance(row["embedding"], str):
                row["embedding"] = json.loads(row["embedding"])

        return rows


async def get_watch_history(user_id: str, limit: int = 50) -> list[dict]:
    """
    Fetch watch history for authenticated user.

    SQL equivalent:
    SELECT id, video_id, watch_duration_seconds, started_at
    FROM watch_history
    WHERE user_id = {user_id}
    ORDER BY started_at DESC
    LIMIT {limit}

    Returns: [
        {"id": "watch-uuid", "video_id": "row-uuid", "watch_duration_seconds": 45, ...},
        ...
    ]

    Note: watch_history.video_id references videos.id (UUID), not YouTube video_id!
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/watch_history",
            headers=HEADERS,
            params={
                "select": "id,video_id,watch_duration_seconds,started_at",
                "user_id": f"eq.{user_id}",
                "order": "started_at.desc",
                "limit": limit
            }
        )
        response.raise_for_status()
        return response.json()


async def get_all_country_embeddings(country_code: str) -> list[list[float]]:
    """
    Fetch ALL embeddings for given country.
    Used in Phase 3 Bucket B for country affinity calculation.

    SQL equivalent:
    SELECT embedding FROM videos
    WHERE country_code = {country_code}
    LIMIT 5000
    """
    import json

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={
                "select": "embedding",
                "country_code": f"eq.{country_code}",
                "limit": 5000
            }
        )
        response.raise_for_status()
        rows = response.json()

        embeddings = []
        for row in rows:
            embedding = row.get("embedding")
            # Parse if it's a string (REST API serializes as JSON string)
            if embedding and isinstance(embedding, str):
                embedding = json.loads(embedding)
            if embedding:
                embeddings.append(embedding)

        return embeddings


async def insert_watch_history(
    user_id: Optional[str],
    guest_uuid: Optional[str],
    video_uuid: str  # videos.id (UUID), not video_id (YouTube ID)
) -> str:
    """
    INSERT new watch_history row (duration=0).
    Returns watch_id UUID for later UPDATE.
    """
    from datetime import datetime

    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "user_id": user_id,
            "guest_uuid": guest_uuid,
            "video_id": video_uuid,  # references videos.id
            "watch_duration_seconds": 0
        }
        response = await client.post(
            f"{REST_URL}/watch_history",
            headers={**HEADERS, "Prefer": "return=representation"},
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data[0]["id"]


async def update_watch_history(watch_id: str, watch_duration_seconds: int) -> bool:
    """UPDATE watch_history with actual duration"""
    from datetime import datetime

    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "watch_duration_seconds": watch_duration_seconds,
            "ended_at": datetime.utcnow().isoformat()
        }
        response = await client.patch(
            f"{REST_URL}/watch_history",
            headers=HEADERS,
            params={"id": f"eq.{watch_id}"},
            json=payload
        )
        response.raise_for_status()
        return True


async def get_unique_categories() -> list[str]:
    """
    Fetch distinct category names.

    SQL equivalent:
    SELECT DISTINCT category_name FROM videos
    ORDER BY category_name
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={"select": "category_name", "limit": 1000}
        )
        response.raise_for_status()
        rows = response.json()
        return sorted(set(row["category_name"] for row in rows if row.get("category_name")))
