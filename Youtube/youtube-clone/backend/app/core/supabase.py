from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


def _looks_like_placeholder(value: str) -> bool:
    placeholders = (
        "YOUR_PROJECT_REF",
        "your-anon",
        "your-service",
        "your-jwt",
        "your-project",
    )
    return any(token in value for token in placeholders)


@lru_cache()
def get_supabase_admin() -> Client:
    """Create and cache the backend Supabase client on first use."""
    settings = get_settings()

    if _looks_like_placeholder(settings.supabase_url):
        raise RuntimeError(
            "SUPABASE_URL is still a placeholder. Update backend/.env with your real Supabase project URL."
        )

    if _looks_like_placeholder(settings.supabase_service_key):
        raise RuntimeError(
            "SUPABASE_SERVICE_KEY is still a placeholder. Update backend/.env with your real Supabase service role key."
        )

    return create_client(settings.supabase_url, settings.supabase_service_key)
