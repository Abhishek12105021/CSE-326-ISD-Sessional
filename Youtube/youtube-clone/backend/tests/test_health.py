"""
Tests for the health check endpoint.
"""


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, client):
        """Health endpoint returns healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_includes_auth_provider(self, client):
        """Health endpoint indicates Supabase auth provider."""
        response = client.get("/health")
        data = response.json()
        assert data["auth_provider"] == "supabase"

    def test_health_check_response_structure(self, client):
        """Health endpoint returns expected JSON structure."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "auth_provider" in data
        assert len(data) == 2
