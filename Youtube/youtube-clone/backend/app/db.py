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
    Search videos by semantic similarity using pgvector RPC.

    Calls the search_videos() RPC function in Supabase which:
    1. Takes a 1024-dim query embedding (taste vector)
    2. Computes cosine distance via pgvector <=> operator
    3. Uses HNSW index for fast approximate nearest neighbor search
    4. Returns results ordered by similarity descending
    5. Optionally filters by country

    Args:
        query_embedding: 1024-dim taste vector from user's watch history
        filter_country: Optional country code filter (e.g., "US", "GB")
        match_count: Number of videos to return

    Returns:
        List of video dicts ordered by cosine similarity (best first)
        If RPC fails, falls back to trending videos
    """
    try:
        # Call the search_videos RPC function
        results = await call_rpc(
            "search_videos",
            {
                "query_embedding": query_embedding,
                "filter_country": filter_country,
                "match_count": match_count
            }
        )
        return results if results else []
    except Exception as e:
        # Fallback: if pgvector search fails, return trending videos
        print(f"[WARNING] Semantic search failed: {e}. Falling back to trending videos.")
        return await get_trending_videos(filter_country, match_count, 200, [])


async def get_trending_videos(
    filter_country: Optional[str],
    match_count: int,
    pool_size: int,
    exclude_ids: list[str]
) -> list[dict]:
    """
    Fetch trending videos using RPC function.

    Uses the get_trending() RPC which:
    1. Sorts by velocity_score (not views) - trending metric
    2. Takes top pool_size candidates
    3. Randomly samples match_count from the pool
    4. Excludes already-selected videos (exclude_ids)
    5. This randomization prevents repetitive trending feeds

    Args:
        filter_country: Optional country code filter
        match_count: Number of videos to return
        pool_size: Size of trending pool to sample from
        exclude_ids: Video IDs to exclude from results

    Returns:
        List of trending videos, randomly sampled
    """
    try:
        results = await call_rpc(
            "get_trending",
            {
                "filter_country": filter_country,
                "match_count": match_count,
                "pool_size": pool_size,
                "exclude_ids": exclude_ids if exclude_ids else []
            }
        )
        return results if results else []
    except Exception as e:
        # Fallback: query trending directly via REST API
        print(f"[WARNING] Trending RPC failed: {e}. Falling back to direct query.")
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "select": "*",
                "order": "velocity_score.desc",
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

            # Filter out excluded videos
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


async def get_video_embeddings_for_boot(limit: int = 50000) -> list[dict]:
    """
    Fetch all video embeddings, country codes, and velocity scores for FAISS initialization.

    Called ONCE at server boot to populate in-memory FAISS index.

    SQL equivalent:
    SELECT id, embedding, country_code, velocity_score
    FROM videos
    WHERE embedding IS NOT NULL
    LIMIT {limit}

    Returns:
        List of dicts with keys: id (UUID), embedding (1024-dim list), country_code (str), velocity_score (float)

    Note: This is the only time embeddings are fetched during the entire server lifetime.
    All subsequent requests use the in-memory FAISS index.
    """
    import json

    async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for large fetch
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={
                "select": "id,embedding,country_code,velocity_score",
                "embedding": "not.is.null",  # Only videos with embeddings
                "limit": limit
            }
        )
        response.raise_for_status()
        rows = response.json()

        # Parse embedding if it's a string (REST API serializes as JSON string)
        for row in rows:
            if row.get("embedding") and isinstance(row["embedding"], str):
                row["embedding"] = json.loads(row["embedding"])

        return rows


async def get_videos_metadata_by_uuids(uuids: list[str]) -> list[dict]:
    """
    Fetch video metadata by UUID (NO embeddings).

    This is used by feed generation to fetch only the metadata fields
    needed for response formatting after FAISS returns UUIDs.

    SQL equivalent:
    SELECT id, video_id, title, thumbnail_link, channel_title, views, publish_time, category_name, velocity_score
    FROM videos
    WHERE id IN (uuids)

    Returns:
        List of video dicts with metadata fields only (no embedding field)

    Performance: ~100ms for 30 videos via REST API
    """
    if not uuids:
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={
                "select": "id,video_id,title,thumbnail_link,channel_title,views,likes,publish_time,category_name,velocity_score",
                "id": f"in.({','.join(uuids)})",
                "limit": len(uuids)
            }
        )
        response.raise_for_status()
        return response.json()


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


async def get_watch_record_by_id(watch_id: str) -> Optional[dict]:
    """
    Fetch a specific watch history record by ID to get the video_id.
    Used when deleting a watch record to decrement views.

    SQL equivalent:
    SELECT id, video_id FROM watch_history WHERE id = {watch_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/watch_history",
            headers=HEADERS,
            params={
                "select": "id,video_id",
                "id": f"eq.{watch_id}"
            }
        )
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            return data[0]
        return None


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
    UPSERT watch_history row (duration=0).
    If an entry already exists for this user+video, resets it for the new session.
    Returns watch_id UUID for later UPDATE.
    """
    from datetime import datetime

    now = datetime.utcnow().isoformat()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Look up existing entry for this user+video combination
        if user_id:
            lookup_params = {"user_id": f"eq.{user_id}", "video_id": f"eq.{video_uuid}", "select": "id", "limit": "1"}
        else:
            lookup_params = {"guest_uuid": f"eq.{guest_uuid}", "video_id": f"eq.{video_uuid}", "select": "id", "limit": "1"}

        try:
            check_resp = await client.get(
                f"{REST_URL}/watch_history",
                headers=HEADERS,
                params=lookup_params
            )
            existing = check_resp.json() if check_resp.status_code == 200 else []

            if existing:
                # Existing entry: reset for new watch session, reuse same watch_id
                watch_id = existing[0]["id"]
                await client.patch(
                    f"{REST_URL}/watch_history",
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    params={"id": f"eq.{watch_id}"},
                    json={"watch_duration_seconds": 0, "started_at": now}
                )
                print(f"[DEBUG] insert_watch_history - reusing existing watch_id {watch_id} for re-watch")
                return watch_id

            # No existing entry: insert a new row
            payload = {
                "user_id": user_id,
                "video_id": video_uuid,
                "watch_duration_seconds": 0,
                "started_at": now,
            }
            if guest_uuid:
                payload["guest_uuid"] = guest_uuid

            response = await client.post(
                f"{REST_URL}/watch_history",
                headers={**HEADERS, "Prefer": "return=representation"},
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data[0]["id"]

        except Exception as e:
            print(f"[ERROR] insert_watch_history failed - user_id: {user_id}, video_uuid: {video_uuid}, error: {e}")
            raise


async def update_watch_history(watch_id: str, watch_duration_seconds: int) -> bool:
    """
    UPDATE watch_history with actual duration.

    Args:
        watch_id: The watch record ID to update
        watch_duration_seconds: How long the user actually watched

    Returns:
        True if successful, False otherwise
    """
    from datetime import datetime

    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "watch_duration_seconds": watch_duration_seconds,
            "ended_at": datetime.utcnow().isoformat()
        }

        try:
            print(f"[DEBUG] Updating watch_history - watch_id: {watch_id}, watch_duration_seconds: {watch_duration_seconds}")
            response = await client.patch(
                f"{REST_URL}/watch_history",
                headers=HEADERS,
                params={"id": f"eq.{watch_id}"},
                json=payload
            )
            response.raise_for_status()
            print(f"[DEBUG] Successfully updated watch_history")
            return True
        except Exception as e:
            print(f"[ERROR] update_watch_history PATCH failed - watch_id: {watch_id}, payload: {payload}")
            print(f"[ERROR] Response status: {response.status_code if 'response' in locals() else 'N/A'}")
            print(f"[ERROR] Response text: {response.text if 'response' in locals() else 'N/A'}")
            raise


async def delete_watch_history(watch_id: str) -> bool:
    """
    DELETE watch_history record by ID.

    Args:
        watch_id: The watch record ID to delete

    Returns:
        True if successful, False otherwise
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(
                f"{REST_URL}/watch_history",
                headers=HEADERS,
                params={"id": f"eq.{watch_id}"}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[ERROR] delete_watch_history failed - watch_id: {watch_id}")
            print(f"[ERROR] Response status: {response.status_code if 'response' in locals() else 'N/A'}")
            print(f"[ERROR] Response text: {response.text if 'response' in locals() else 'N/A'}")
            raise


async def get_videos_by_categories(
    categories: list[str],
    excluded_ids: list[str] = None,
    limit: int = 30
) -> list[dict]:
    """
    Fetch videos filtered by one or more category names, ordered by velocity then views.

    SQL equivalent:
    SELECT id, video_id, title, ...
    FROM videos
    WHERE category_name IN (categories)
      AND id NOT IN (excluded_ids)
    ORDER BY velocity_score DESC NULLS LAST, views DESC
    LIMIT limit
    """
    if not categories:
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Quote each category name so values with spaces/& are handled correctly
        quoted_cats = ",".join(f'"{c}"' for c in categories)

        params = {
            "select": "id,video_id,title,thumbnail_link,channel_title,views,likes,publish_time,category_name,velocity_score",
            "category_name": f"in.({quoted_cats})",
            "order": "velocity_score.desc.nullslast,views.desc",
            "limit": str(limit),
        }

        if excluded_ids:
            params["id"] = f"not.in.({','.join(excluded_ids)})"

        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params=params
        )
        response.raise_for_status()
        return response.json()


async def get_videos_by_regions(
    regions: list[str],
    excluded_ids: list[str] = None,
    limit: int = 30
) -> list[dict]:
    """
    Fetch videos filtered by one or more region codes, ordered by velocity then views.

    SQL equivalent:
    SELECT id, video_id, title, ...
    FROM videos
    WHERE country_code IN (regions)
      AND id NOT IN (excluded_ids)
    ORDER BY velocity_score DESC NULLS LAST, views DESC
    LIMIT limit
    """
    if not regions:
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Quote each region code for safe IN filtering.
        quoted_regions = ",".join(f'"{r}"' for r in regions)

        params = {
            "select": "id,video_id,title,thumbnail_link,channel_title,views,likes,publish_time,category_name,velocity_score,country_code",
            "country_code": f"in.({quoted_regions})",
            "order": "velocity_score.desc.nullslast,views.desc",
            "limit": str(limit),
        }

        if excluded_ids:
            params["id"] = f"not.in.({','.join(excluded_ids)})"

        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params=params
        )
        response.raise_for_status()
        return response.json()


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


# ======================== VIEW COUNT MANAGEMENT ========================


async def increment_video_views(video_id: str) -> bool:
    """
    Increment the view count for a video.

    SQL equivalent:
    UPDATE videos SET views = views + 1 WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current view count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "views",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data or len(data) == 0:
                return False

            current_views = data[0]["views"] or 0
            new_views = current_views + 1

            # Update with new count
            response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"views": new_views}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[ERROR] increment_video_views failed for video {video_id}: {e}")
            return False


async def decrement_video_views(video_id: str) -> bool:
    """
    Decrement the view count for a video (when watch history is deleted).

    SQL equivalent:
    UPDATE videos SET views = GREATEST(0, views - 1) WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current view count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "views",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data or len(data) == 0:
                return False

            current_views = data[0]["views"] or 0
            new_views = max(0, current_views - 1)  # Don't go below 0

            # Update with new count
            response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"views": new_views}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[ERROR] decrement_video_views failed for video {video_id}: {e}")
            return False


# ======================== LIKES MANAGEMENT ========================


async def increment_video_likes(video_id: str) -> bool:
    """
    Increment the like count for a video.

    SQL equivalent:
    UPDATE videos SET likes = likes + 1 WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current like count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "likes",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                print(f"[WARNING] Video {video_id} not found")
                return False

            current_likes = data[0].get("likes", 0) or 0
            new_likes = current_likes + 1

            # Update with new value
            update_response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"likes": new_likes}
            )

            print(f"[DEBUG] increment_video_likes - Video: {video_id}, Old: {current_likes}, New: {new_likes}, Status: {update_response.status_code}")
            return update_response.status_code in (200, 204)
        except Exception as e:
            print(f"[ERROR] increment_video_likes failed for {video_id}: {e}")
            return False


async def decrement_video_likes(video_id: str) -> bool:
    """
    Decrement the like count for a video (min 0).

    SQL equivalent:
    UPDATE videos SET likes = MAX(0, likes - 1) WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current like count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "likes",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                print(f"[WARNING] Video {video_id} not found")
                return False

            current_likes = data[0].get("likes", 0) or 0
            new_likes = max(0, current_likes - 1)  # Don't go below 0

            # Update with new value
            update_response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"likes": new_likes}
            )

            print(f"[DEBUG] decrement_video_likes - Video: {video_id}, Old: {current_likes}, New: {new_likes}, Status: {update_response.status_code}")
            return update_response.status_code in (200, 204)
        except Exception as e:
            print(f"[ERROR] decrement_video_likes failed for {video_id}: {e}")
            return False


async def increment_video_dislikes(video_id: str) -> bool:
    """
    Increment the dislike count for a video.

    SQL equivalent:
    UPDATE videos SET dislikes = dislikes + 1 WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current dislike count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "dislikes",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                print(f"[WARNING] Video {video_id} not found")
                return False

            current_dislikes = data[0].get("dislikes", 0) or 0
            new_dislikes = current_dislikes + 1

            # Update with new value
            update_response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"dislikes": new_dislikes}
            )

            print(f"[DEBUG] increment_video_dislikes - Video: {video_id}, Old: {current_dislikes}, New: {new_dislikes}, Status: {update_response.status_code}")
            return update_response.status_code in (200, 204)
        except Exception as e:
            print(f"[ERROR] increment_video_dislikes failed for {video_id}: {e}")
            return False


async def decrement_video_dislikes(video_id: str) -> bool:
    """
    Decrement the dislike count for a video (min 0).

    SQL equivalent:
    UPDATE videos SET dislikes = MAX(0, dislikes - 1) WHERE id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First get current dislike count
            response = await client.get(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={
                    "select": "dislikes",
                    "id": f"eq.{video_id}"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                print(f"[WARNING] Video {video_id} not found")
                return False

            current_dislikes = data[0].get("dislikes", 0) or 0
            new_dislikes = max(0, current_dislikes - 1)  # Don't go below 0

            # Update with new value
            update_response = await client.patch(
                f"{REST_URL}/videos",
                headers=HEADERS,
                params={"id": f"eq.{video_id}"},
                json={"dislikes": new_dislikes}
            )

            print(f"[DEBUG] decrement_video_dislikes - Video: {video_id}, Old: {current_dislikes}, New: {new_dislikes}, Status: {update_response.status_code}")
            return update_response.status_code in (200, 204)
        except Exception as e:
            print(f"[ERROR] decrement_video_dislikes failed for {video_id}: {e}")
            return False




async def get_user_liked_videos(user_id: str, limit: int = 100) -> list[dict]:
    """
    Fetch all videos liked by user.

    SQL equivalent:
    SELECT v.* FROM videos v
    JOIN liked_videos lv ON v.id = lv.video_id
    WHERE lv.user_id = {user_id}
    ORDER BY lv.liked_at DESC
    LIMIT {limit}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First get liked video IDs from liked_videos
        response = await client.get(
            f"{REST_URL}/liked_videos",
            headers=HEADERS,
            params={
                "select": "video_id",
                "user_id": f"eq.{user_id}",
                "order": "liked_at.desc",
                "limit": limit
            }
        )
        response.raise_for_status()
        likes = response.json()

        if not likes:
            return []

        # Extract video IDs and fetch full video data
        video_ids = [like["video_id"] for like in likes]
        return await get_videos_by_uuids(video_ids)


async def get_user_liked_videos_with_timestamps(user_id: str, limit: int = 500) -> list[dict]:
    """
    Fetch liked videos WITH liked_at timestamps for recommendation weighting.

    SQL equivalent:
    SELECT video_id, liked_at FROM liked_videos
    WHERE user_id = {user_id}
    ORDER BY liked_at DESC
    LIMIT {limit}

    Returns: [
        {"video_id": "uuid-...", "liked_at": "2026-03-25T10:30:00+00:00"},
        ...
    ]

    Note: Returns raw liked_videos rows with timestamps, NOT joined video data.
    Embeddings are fetched separately via get_videos_by_uuids().
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/liked_videos",
            headers=HEADERS,
            params={
                "select": "video_id,liked_at",
                "user_id": f"eq.{user_id}",
                "order": "liked_at.desc",
                "limit": limit
            }
        )
        response.raise_for_status()
        return response.json()


async def add_like(user_id: str, video_id: str) -> bool:
    """
    Add a like for a video and increment video's like count.
    If video was previously disliked, remove the dislike first.

    SQL equivalent:
    INSERT INTO liked_videos (user_id, video_id, liked_at)
    VALUES ({user_id}, {video_id}, NOW())
    ON CONFLICT DO NOTHING
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check if video was disliked
        is_disliked = await is_video_disliked(user_id, video_id)

        if is_disliked:
            print(f"[DEBUG] Video was disliked, removing dislike first")
            await remove_dislike(user_id, video_id)

        payload = {
            "user_id": user_id,
            "video_id": video_id
        }
        try:
            response = await client.post(
                f"{REST_URL}/liked_videos",
                headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"},
                json=payload
            )

            print(f"[DEBUG] add_like response status: {response.status_code}")
            print(f"[DEBUG] add_like response body: {response.text}")

            # 201 = created, 409 = conflict (already liked), both are success
            if response.status_code in (200, 201, 409):
                # Only increment if this is a new like (status 201), not a duplicate (409)
                if response.status_code == 201:
                    print(f"[DEBUG] New like created, incrementing video like count")
                    await increment_video_likes(video_id)
                elif response.status_code == 409:
                    print(f"[DEBUG] Like already exists (conflict), skipping increment")
                return True
            return False
        except Exception as e:
            print(f"[ERROR] add_like exception: {e}")
            return False


async def remove_like(user_id: str, video_id: str) -> bool:
    """
    Remove a like for a video and decrement video's like count.

    SQL equivalent:
    DELETE FROM liked_videos
    WHERE user_id = {user_id} AND video_id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{REST_URL}/liked_videos",
            headers={**HEADERS, "Prefer": "return=representation"},
            params={
                "user_id": f"eq.{user_id}",
                "video_id": f"eq.{video_id}"
            }
        )

        print(f"[DEBUG] remove_like response status: {response.status_code}")
        print(f"[DEBUG] remove_like response body: {response.text}")

        # Check if response indicates deletion occurred
        if response.status_code in (200, 204):
            # For status 200, check if any rows were deleted (response body should be empty array or have data)
            if response.status_code == 200:
                try:
                    data = response.json()
                    deleted_count = len(data) if isinstance(data, list) else 1
                    print(f"[DEBUG] Deleted {deleted_count} rows")
                    # Only decrement if a like was actually deleted
                    if deleted_count > 0:
                        await decrement_video_likes(video_id)
                    return deleted_count > 0
                except:
                    # If we can't parse response but got 200, assume success and decrement
                    await decrement_video_likes(video_id)
                    return True
            # 204 No Content also indicates success, but we don't know if a row was deleted
            # To be safe, we'll decrement only if we have confirmation
            return True

        print(f"[ERROR] Delete failed with status {response.status_code}")
        return False


async def is_video_liked(user_id: str, video_id: str) -> bool:
    """
    Check if user has liked a video.

    SQL equivalent:
    SELECT EXISTS(
        SELECT 1 FROM liked_videos
        WHERE user_id = {user_id} AND video_id = {video_id}
    )
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/liked_videos",
            headers=HEADERS,
            params={
                "user_id": f"eq.{user_id}",
                "video_id": f"eq.{video_id}",
                "select": "id"
            }
        )

        if response.status_code == 200:
            data = response.json()
            return len(data) > 0
        return False


# ======================== DISLIKES MANAGEMENT ========================


async def get_user_disliked_videos(user_id: str, limit: int = 100) -> list[dict]:
    """
    Fetch all videos disliked by user.

    SQL equivalent:
    SELECT v.* FROM videos v
    JOIN disliked_videos dv ON v.id = dv.video_id
    WHERE dv.user_id = {user_id}
    ORDER BY dv.disliked_at DESC
    LIMIT {limit}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First get disliked video IDs from disliked_videos
        response = await client.get(
            f"{REST_URL}/disliked_videos",
            headers=HEADERS,
            params={
                "select": "video_id",
                "user_id": f"eq.{user_id}",
                "order": "disliked_at.desc",
                "limit": limit
            }
        )
        response.raise_for_status()
        dislikes = response.json()

        if not dislikes:
            return []

        # Extract video IDs and fetch full video data
        video_ids = [dislike["video_id"] for dislike in dislikes]
        return await get_videos_by_uuids(video_ids)


async def add_dislike(user_id: str, video_id: str) -> bool:
    """
    Add a dislike for a video and increment video's dislike count.
    If video was previously liked, remove the like first.

    SQL equivalent:
    INSERT INTO disliked_videos (user_id, video_id, disliked_at)
    VALUES ({user_id}, {video_id}, NOW())
    ON CONFLICT DO NOTHING
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check if video was liked
        is_liked = await is_video_liked(user_id, video_id)

        if is_liked:
            print(f"[DEBUG] Video was liked, removing like first")
            await remove_like(user_id, video_id)

        payload = {
            "user_id": user_id,
            "video_id": video_id
        }
        try:
            response = await client.post(
                f"{REST_URL}/disliked_videos",
                headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"},
                json=payload
            )

            print(f"[DEBUG] add_dislike response status: {response.status_code}")
            print(f"[DEBUG] add_dislike response body: {response.text}")

            # 201 = created, 409 = conflict (already disliked), both are success
            if response.status_code in (200, 201, 409):
                # Only increment if this is a new dislike (status 201), not a duplicate (409)
                if response.status_code == 201:
                    print(f"[DEBUG] New dislike created, incrementing video dislike count")
                    await increment_video_dislikes(video_id)
                elif response.status_code == 409:
                    print(f"[DEBUG] Dislike already exists (conflict), skipping increment")
                return True
            return False
        except Exception as e:
            print(f"[ERROR] add_dislike exception: {e}")
            return False


async def remove_dislike(user_id: str, video_id: str) -> bool:
    """
    Remove a dislike for a video and decrement video's dislike count.

    SQL equivalent:
    DELETE FROM disliked_videos
    WHERE user_id = {user_id} AND video_id = {video_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{REST_URL}/disliked_videos",
            headers={**HEADERS, "Prefer": "return=representation"},
            params={
                "user_id": f"eq.{user_id}",
                "video_id": f"eq.{video_id}"
            }
        )

        print(f"[DEBUG] remove_dislike response status: {response.status_code}")
        print(f"[DEBUG] remove_dislike response body: {response.text}")

        # Check if response indicates deletion occurred
        if response.status_code in (200, 204):
            # For status 200, check if any rows were deleted (response body should be empty array or have data)
            if response.status_code == 200:
                try:
                    data = response.json()
                    deleted_count = len(data) if isinstance(data, list) else 1
                    print(f"[DEBUG] Deleted {deleted_count} rows")
                    # Only decrement if a dislike was actually deleted
                    if deleted_count > 0:
                        await decrement_video_dislikes(video_id)
                    return deleted_count > 0
                except:
                    # If we can't parse response but got 200, assume success and decrement
                    await decrement_video_dislikes(video_id)
                    return True
            # 204 No Content also indicates success, but we don't know if a row was deleted
            # To be safe, we'll decrement only if we have confirmation
            return True

        print(f"[ERROR] Delete failed with status {response.status_code}")
        return False


async def is_video_disliked(user_id: str, video_id: str) -> bool:
    """
    Check if user has disliked a video.

    SQL equivalent:
    SELECT EXISTS(
        SELECT 1 FROM disliked_videos
        WHERE user_id = {user_id} AND video_id = {video_id}
    )
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/disliked_videos",
            headers=HEADERS,
            params={
                "user_id": f"eq.{user_id}",
                "video_id": f"eq.{video_id}",
                "select": "id"
            }
        )

        if response.status_code == 200:
            data = response.json()
            return len(data) > 0
        return False


# ======================== SUBSCRIPTIONS MANAGEMENT ========================


async def get_all_channels() -> list[str]:
    """
    Fetch all unique channel titles from videos table.

    SQL equivalent:
    SELECT DISTINCT channel_title FROM videos
    ORDER BY channel_title
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/videos",
            headers=HEADERS,
            params={"select": "channel_title", "limit": 5000}
        )
        response.raise_for_status()
        rows = response.json()
        return sorted(set(row["channel_title"] for row in rows if row.get("channel_title")))


async def get_user_subscribed_channels(user_id: str, limit: int = 100) -> list[str]:
    """
    Fetch all channels subscribed by user.

    SQL equivalent:
    SELECT DISTINCT channel_id FROM subscriptions
    WHERE user_id = {user_id}
    ORDER BY created_at DESC
    LIMIT {limit}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/subscriptions",
            headers=HEADERS,
            params={
                "select": "channel_id",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
                "limit": limit
            }
        )
        response.raise_for_status()
        subscriptions = response.json()

        if not subscriptions:
            return []

        # Return list of unique channel IDs
        return [sub["channel_id"] for sub in subscriptions]


async def subscribe(user_id: str, channel_id: str) -> bool:
    """
    Subscribe user to a channel.

    SQL equivalent:
    INSERT INTO subscriptions (user_id, channel_id, created_at)
    VALUES ({user_id}, {channel_id}, NOW())
    ON CONFLICT DO NOTHING
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "user_id": user_id,
            "channel_id": channel_id
        }
        try:
            response = await client.post(
                f"{REST_URL}/subscriptions",
                headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"},
                json=payload
            )

            print(f"[DEBUG] subscribe response status: {response.status_code}")
            print(f"[DEBUG] subscribe response body: {response.text}")

            # 201 = created, 409 = conflict (already subscribed), both are success
            return response.status_code in (200, 201, 409)
        except Exception as e:
            print(f"[ERROR] subscribe exception: {e}")
            return False


async def unsubscribe(user_id: str, channel_id: str) -> bool:
    """
    Unsubscribe user from a channel.

    SQL equivalent:
    DELETE FROM subscriptions
    WHERE user_id = {user_id} AND channel_id = {channel_id}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{REST_URL}/subscriptions",
            headers={**HEADERS, "Prefer": "return=representation"},
            params={
                "user_id": f"eq.{user_id}",
                "channel_id": f"eq.{channel_id}"
            }
        )

        print(f"[DEBUG] unsubscribe response status: {response.status_code}")
        print(f"[DEBUG] unsubscribe response body: {response.text}")

        # Check if response indicates deletion occurred
        if response.status_code in (200, 204):
            # For status 200, check if any rows were deleted
            if response.status_code == 200:
                try:
                    data = response.json()
                    deleted_count = len(data) if isinstance(data, list) else 1
                    print(f"[DEBUG] Deleted {deleted_count} subscription rows")
                    return deleted_count > 0
                except:
                    return True  # 200 OK means deletion was processed
            # 204 No Content also indicates success
            return True

        print(f"[ERROR] Unsubscribe failed with status {response.status_code}")
        return False


async def is_subscribed(user_id: str, channel_id: str) -> bool:
    """
    Check if user is subscribed to a channel.

    SQL equivalent:
    SELECT EXISTS(
        SELECT 1 FROM subscriptions
        WHERE user_id = {user_id} AND channel_id = {channel_id}
    )
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{REST_URL}/subscriptions",
            headers=HEADERS,
            params={
                "user_id": f"eq.{user_id}",
                "channel_id": f"eq.{channel_id}",
                "select": "id"
            }
        )

        if response.status_code == 200:
            data = response.json()
            return len(data) > 0
        return False


