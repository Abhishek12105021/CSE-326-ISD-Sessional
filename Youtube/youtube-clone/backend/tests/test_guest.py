"""
Tests for guest endpoints (/api/guest/*).
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import numpy as np


class TestGuestSession:
    """Tests for POST /api/guest/session endpoint."""

    def test_create_guest_session_returns_200(self, client, guest_uuid):
        """Guest session endpoint returns 200."""
        response = client.post(
            "/api/guest/session",
            json={"guest_uuid": guest_uuid}
        )
        assert response.status_code == 200

    def test_create_guest_session_echoes_uuid(self, client, guest_uuid):
        """Guest session endpoint echoes back the guest_uuid."""
        response = client.post(
            "/api/guest/session",
            json={"guest_uuid": guest_uuid}
        )
        data = response.json()
        assert data["guest_uuid"] == guest_uuid

    def test_create_guest_session_returns_zero_interactions(self, client, guest_uuid):
        """Guest session endpoint returns interaction_count=0."""
        response = client.post(
            "/api/guest/session",
            json={"guest_uuid": guest_uuid}
        )
        data = response.json()
        assert data["interaction_count"] == 0

    def test_create_guest_session_includes_timestamp(self, client, guest_uuid):
        """Guest session endpoint includes created_at timestamp."""
        response = client.post(
            "/api/guest/session",
            json={"guest_uuid": guest_uuid}
        )
        data = response.json()
        assert "created_at" in data


class TestGuestFeed:
    """Tests for POST /api/guest/feed endpoint."""

    def test_guest_feed_returns_200(self, client, guest_uuid, sample_videos):
        """Guest feed endpoint returns 200."""
        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/feed",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "limit": 5,
                        "watched_video_ids": []
                    }
                )
                assert response.status_code == 200

    def test_guest_feed_cold_start_strategy(self, client, guest_uuid, sample_videos):
        """Guest feed with no watch history returns phase_1_cold_start."""
        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/feed",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "limit": 5,
                        "watched_video_ids": []
                    }
                )
                data = response.json()
                assert data["strategy"] == "phase_1_cold_start"
                assert data["interaction_count"] == 0

    def test_guest_feed_warm_up_strategy(self, client, guest_uuid, sample_videos):
        """Guest feed with 1-4 interactions returns phase_2_warm_up."""
        watched_ids = [str(uuid4()) for _ in range(3)]

        with patch("app.api.routes.guest.faiss_manager") as mock_faiss:
            with patch("app.api.routes.guest.generate_phase2_feed", new_callable=AsyncMock) as mock_gen:
                with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                    # Mock embedding lookup
                    mock_faiss.UUID_TO_EMBEDDING = {
                        uid: np.random.randn(1024).astype(np.float32) for uid in watched_ids
                    }
                    mock_gen.return_value = [v["id"] for v in sample_videos]
                    mock_meta.return_value = sample_videos

                    response = client.post(
                        "/api/guest/feed",
                        json={
                            "guest_uuid": guest_uuid,
                            "region": "US",
                            "limit": 5,
                            "watched_video_ids": watched_ids
                        }
                    )
                    data = response.json()
                    assert data["strategy"] == "phase_2_warm_up"
                    assert data["interaction_count"] == 3

    def test_guest_feed_personalized_strategy(self, client, guest_uuid, sample_videos):
        """Guest feed with 5+ interactions returns phase_3_personalized."""
        watched_ids = [str(uuid4()) for _ in range(7)]

        with patch("app.api.routes.guest.faiss_manager") as mock_faiss:
            with patch("app.api.routes.guest.generate_phase3_feed", new_callable=AsyncMock) as mock_gen:
                with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                    mock_faiss.UUID_TO_EMBEDDING = {
                        uid: np.random.randn(1024).astype(np.float32) for uid in watched_ids
                    }
                    mock_gen.return_value = [v["id"] for v in sample_videos]
                    mock_meta.return_value = sample_videos

                    response = client.post(
                        "/api/guest/feed",
                        json={
                            "guest_uuid": guest_uuid,
                            "region": "US",
                            "limit": 5,
                            "watched_video_ids": watched_ids
                        }
                    )
                    data = response.json()
                    assert data["strategy"] == "phase_3_personalized"
                    assert data["interaction_count"] == 7

    def test_guest_feed_returns_videos(self, client, guest_uuid, sample_videos):
        """Guest feed returns video list with correct structure."""
        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/feed",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "limit": 5,
                        "watched_video_ids": []
                    }
                )
                data = response.json()
                assert "videos" in data
                assert len(data["videos"]) == 5
                assert data["total"] == 5

    def test_guest_feed_video_structure(self, client, guest_uuid, sample_videos):
        """Guest feed videos have expected structure."""
        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/feed",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "limit": 5,
                        "watched_video_ids": []
                    }
                )
                data = response.json()
                video = data["videos"][0]

                # Check required fields
                assert "id" in video
                assert "video_id" in video
                assert "title" in video
                assert "thumbnail" in video
                assert "channel" in video
                assert "views" in video


class TestGuestReload:
    """Tests for POST /api/guest/reload endpoint."""

    def test_guest_reload_returns_200(self, client, guest_uuid, sample_videos):
        """Guest reload endpoint returns 200."""
        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/reload",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "watched_video_ids": [],
                        "excluded_video_ids": [],
                        "limit": 5
                    }
                )
                assert response.status_code == 200

    def test_guest_reload_excludes_videos(self, client, guest_uuid, sample_videos):
        """Guest reload excludes previously shown videos."""
        excluded_ids = [str(uuid4()) for _ in range(10)]

        with patch("app.api.routes.guest.generate_phase1_feed", new_callable=AsyncMock) as mock_gen:
            with patch("app.api.routes.guest.get_videos_metadata_by_uuids", new_callable=AsyncMock) as mock_meta:
                mock_gen.return_value = [v["id"] for v in sample_videos]
                mock_meta.return_value = sample_videos

                response = client.post(
                    "/api/guest/reload",
                    json={
                        "guest_uuid": guest_uuid,
                        "region": "US",
                        "watched_video_ids": [],
                        "excluded_video_ids": excluded_ids,
                        "limit": 5
                    }
                )
                assert response.status_code == 200
                # Verify generate was called with exclusions
                mock_gen.assert_called_once()
                call_args = mock_gen.call_args
                assert len(call_args[0][1]) == len(excluded_ids)  # all_excluded list


class TestGuestWatch:
    """Tests for POST /api/guest/watch endpoint."""

    def test_guest_watch_insert_returns_200(self, client, guest_uuid, sample_video):
        """Guest watch INSERT returns 200 with watch_id."""
        with patch("app.api.routes.guest.insert_watch_history", new_callable=AsyncMock) as mock_insert:
            with patch("app.api.routes.guest.increment_video_views", new_callable=AsyncMock) as mock_inc:
                watch_id = str(uuid4())
                mock_insert.return_value = watch_id
                mock_inc.return_value = True

                response = client.post(
                    "/api/guest/watch",
                    json={
                        "video_uuid": sample_video["id"],
                        "guest_uuid": guest_uuid
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["watch_id"] == watch_id
                assert data["success"] is True

    def test_guest_watch_insert_increments_views(self, client, guest_uuid, sample_video):
        """Guest watch INSERT increments video view count."""
        with patch("app.api.routes.guest.insert_watch_history", new_callable=AsyncMock) as mock_insert:
            with patch("app.api.routes.guest.increment_video_views", new_callable=AsyncMock) as mock_inc:
                mock_insert.return_value = str(uuid4())
                mock_inc.return_value = True

                client.post(
                    "/api/guest/watch",
                    json={
                        "video_uuid": sample_video["id"],
                        "guest_uuid": guest_uuid
                    }
                )
                mock_inc.assert_called_once_with(sample_video["id"])

    def test_guest_watch_update_returns_200(self, client, guest_uuid, sample_video):
        """Guest watch UPDATE returns 200."""
        watch_id = str(uuid4())

        with patch("app.api.routes.guest.update_watch_history", new_callable=AsyncMock):
            response = client.post(
                "/api/guest/watch",
                json={
                    "video_uuid": sample_video["id"],
                    "guest_uuid": guest_uuid,
                    "watch_id": watch_id,
                    "watch_duration_seconds": 120
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["watch_id"] == watch_id
            assert data["success"] is True

    def test_guest_watch_update_calls_update_history(self, client, guest_uuid, sample_video):
        """Guest watch UPDATE calls update_watch_history with duration."""
        watch_id = str(uuid4())

        with patch("app.api.routes.guest.update_watch_history", new_callable=AsyncMock) as mock_update:
            client.post(
                "/api/guest/watch",
                json={
                    "video_uuid": sample_video["id"],
                    "guest_uuid": guest_uuid,
                    "watch_id": watch_id,
                    "watch_duration_seconds": 120
                }
            )
            mock_update.assert_called_once_with(
                watch_id=watch_id,
                watch_duration_seconds=120
            )
