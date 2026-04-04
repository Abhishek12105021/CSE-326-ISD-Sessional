"""
Pytest fixtures and configuration for backend tests.

Mocks heavy dependencies (FAISS, embedding service, Supabase) for fast unit tests.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Set test environment variables BEFORE importing app
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["SUPABASE_SERVICE_KEY"] = "test-service-key"
os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

# Create mock modules BEFORE importing app
mock_faiss_manager = MagicMock()
mock_faiss_manager.initialize_faiss = AsyncMock()
mock_faiss_manager.get_index_stats = MagicMock(return_value={
    "total_videos": 1000,
    "memory_mb_videos": 50.0
})
mock_faiss_manager.UUID_TO_EMBEDDING = {}
mock_faiss_manager.VIDEO_INDEX = MagicMock()

mock_embedding_service = MagicMock()
mock_embedding_service.load_model = AsyncMock()
mock_embedding_service.embed_query = AsyncMock(return_value=[0.1] * 1024)

# Inject mocks into sys.modules
sys.modules["app.core.faiss_manager"] = mock_faiss_manager
sys.modules["app.core.embedding_service"] = mock_embedding_service


@pytest.fixture(scope="session")
def app():
    """Create FastAPI app with mocked dependencies."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_current_user():
    """Mock authenticated user for auth-required endpoints."""
    return {
        "id": str(uuid4()),
        "email": "test@example.com",
        "display_name": "Test User",
        "avatar_url": "https://example.com/avatar.png",
        "created_at": "2026-01-01T00:00:00Z"
    }


@pytest.fixture
def mock_db_user(mock_current_user):
    """Mock database user record."""
    return {
        "id": mock_current_user["id"],
        "email": mock_current_user["email"],
        "display_name": mock_current_user["display_name"],
        "avatar_url": mock_current_user["avatar_url"],
        "region": "US"
    }


@pytest.fixture
def sample_video():
    """Sample video data for testing."""
    return {
        "id": str(uuid4()),
        "video_id": "dQw4w9WgXcQ",
        "title": "Test Video Title",
        "thumbnail_link": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "channel_title": "Test Channel",
        "views": 1000000,
        "likes": 50000,
        "publish_time": "2024-01-15T12:00:00Z",
        "category_name": "Music",
        "velocity_score": 0.85
    }


@pytest.fixture
def sample_videos(sample_video):
    """List of sample videos for feed testing."""
    videos = []
    for i in range(5):
        video = sample_video.copy()
        video["id"] = str(uuid4())
        video["title"] = f"Test Video {i + 1}"
        videos.append(video)
    return videos


@pytest.fixture
def guest_uuid():
    """Generate a guest UUID for testing."""
    return str(uuid4())


@pytest.fixture
def auth_headers(mock_current_user):
    """Generate mock auth headers."""
    return {"Authorization": "Bearer test-token"}
