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
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{REST_URL}/users",
            headers=HEADERS,
            params={"id": f"eq.{user_id}", "select": "*"}
        )

        print(f"[DEBUG] get_user_by_id status: {response.status_code}")
        print(f"[DEBUG] get_user_by_id response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]
        return None


async def update_user(user_id: str, updates: dict) -> Optional[dict]:
    """
    Update user in Supabase users table.
    """
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{REST_URL}/users",
            headers=HEADERS,
            params={"id": f"eq.{user_id}"},
            json=updates
        )

        print(f"[DEBUG] update_user status: {response.status_code}")
        print(f"[DEBUG] update_user response: {response.text}")

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
