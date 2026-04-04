"""
Tests for authentication endpoints (/api/auth/*).
"""
from unittest.mock import AsyncMock, patch


class TestAuthProfile:
    """Tests for GET /api/auth/profile endpoint."""

    def test_profile_requires_authentication(self, client):
        """Profile endpoint returns 403 without auth header."""
        response = client.get("/api/auth/profile")
        assert response.status_code == 403

    def test_profile_returns_user_data(self, client, mock_current_user, mock_db_user):
        """Profile endpoint returns user profile when authenticated."""
        with patch("app.api.routes.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_db_user

            from app.api.deps import get_current_user
            from app.main import app
            app.dependency_overrides[get_current_user] = lambda: mock_current_user

            try:
                response = client.get("/api/auth/profile")
                assert response.status_code == 200
                data = response.json()
                assert data["email"] == mock_current_user["email"]
            finally:
                app.dependency_overrides.clear()

    def test_profile_creates_user_if_not_exists(self, client, mock_current_user):
        """Profile endpoint creates user in DB if not found."""
        with patch("app.api.routes.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            with patch("app.api.routes.auth.upsert_user", new_callable=AsyncMock) as mock_upsert:
                mock_get.return_value = None  # User not in DB
                mock_upsert.return_value = {
                    "id": mock_current_user["id"],
                    "email": mock_current_user["email"],
                    "region": ""
                }

                from app.api.deps import get_current_user
                from app.main import app
                app.dependency_overrides[get_current_user] = lambda: mock_current_user

                try:
                    response = client.get("/api/auth/profile")
                    assert response.status_code == 200
                    mock_upsert.assert_called_once()
                finally:
                    app.dependency_overrides.clear()


class TestAuthUpdateProfile:
    """Tests for PUT /api/auth/profile endpoint."""

    def test_update_profile_requires_authentication(self, client):
        """Update profile endpoint returns 403 without auth."""
        response = client.put("/api/auth/profile", json={"region": "US"})
        assert response.status_code == 403

    def test_update_profile_changes_region(self, client, mock_current_user, mock_db_user):
        """Update profile endpoint updates user region."""
        updated_user = mock_db_user.copy()
        updated_user["region"] = "JP"

        with patch("app.api.routes.auth.update_user", new_callable=AsyncMock) as mock_update:
            with patch("app.api.routes.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
                mock_update.return_value = updated_user
                mock_get.return_value = updated_user

                from app.api.deps import get_current_user
                from app.main import app
                app.dependency_overrides[get_current_user] = lambda: mock_current_user

                try:
                    response = client.put(
                        "/api/auth/profile",
                        json={"region": "JP"}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["region"] == "JP"
                finally:
                    app.dependency_overrides.clear()


class TestAuthLogout:
    """Tests for POST /api/auth/logout endpoint."""

    def test_logout_requires_authentication(self, client):
        """Logout endpoint returns 403 without auth."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 403

    def test_logout_returns_success_message(self, client, mock_current_user):
        """Logout endpoint returns success message."""
        from app.api.deps import get_current_user
        from app.main import app
        app.dependency_overrides[get_current_user] = lambda: mock_current_user

        try:
            response = client.post("/api/auth/logout")
            assert response.status_code == 200
            data = response.json()
            assert "Logged out" in data["message"]
        finally:
            app.dependency_overrides.clear()


class TestAuthLogoutAll:
    """Tests for POST /api/auth/logout-all endpoint."""

    def test_logout_all_requires_authentication(self, client):
        """Logout-all endpoint returns 403 without auth."""
        response = client.post("/api/auth/logout-all")
        assert response.status_code == 403

    def test_logout_all_returns_instructions(self, client, mock_current_user):
        """Logout-all endpoint returns instructions for frontend."""
        from app.api.deps import get_current_user
        from app.main import app
        app.dependency_overrides[get_current_user] = lambda: mock_current_user

        try:
            response = client.post("/api/auth/logout-all")
            assert response.status_code == 200
            data = response.json()
            assert "supabase.auth.signOut" in data["message"]
        finally:
            app.dependency_overrides.clear()
