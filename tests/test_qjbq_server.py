"""Tests for qjbq.server — FastAPI notification relay."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# We need to set QJBQ_SESSIONS_DIR *before* importing the app,
# so every test uses a fresh temp directory.


@pytest.fixture()
def client(tmp_path: Path):
    """Create a TestClient with a temp sessions dir."""
    os.environ["QJBQ_SESSIONS_DIR"] = str(tmp_path)
    # Re-import to pick up the env var change
    from qjbq.server import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("QJBQ_SESSIONS_DIR", None)


@pytest.fixture()
def sessions_dir(tmp_path: Path) -> Path:
    """Return the temp sessions dir (same as what client uses)."""
    return tmp_path


# ── Health ───────────────────────────────────────────────────────────

class TestHealth:
    def test_health_status(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_version(self, client):
        r = client.get("/health")
        data = r.json()
        assert data["version"] == "0.1.0"


# ── POST /api/notify ─────────────────────────────────────────────────

class TestPostNotify:
    def test_write_creates_file(self, client, sessions_dir):
        r = client.post("/api/notify", json={
            "session_id": "sess-001",
            "app": "alert",
            "content": "# Alert\nSomething happened.",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["chars"] == len("# Alert\nSomething happened.")
        # File should exist on disk
        f = sessions_dir / "sess-001" / "core" / "apps" / "alert.md"
        assert f.exists()
        assert f.read_text() == "# Alert\nSomething happened."

    def test_write_overwrites_existing(self, client, sessions_dir):
        client.post("/api/notify", json={
            "session_id": "sess-002",
            "app": "status",
            "content": "v1",
        })
        client.post("/api/notify", json={
            "session_id": "sess-002",
            "app": "status",
            "content": "v2 updated",
        })
        f = sessions_dir / "sess-002" / "core" / "apps" / "status.md"
        assert f.read_text() == "v2 updated"

    def test_write_empty_session_id_rejected(self, client):
        r = client.post("/api/notify", json={
            "session_id": "",
            "app": "test",
            "content": "hello",
        })
        assert r.status_code == 422  # validation error

    def test_write_empty_content_rejected(self, client):
        r = client.post("/api/notify", json={
            "session_id": "sess-003",
            "app": "test",
            "content": "",
        })
        assert r.status_code == 422

    def test_write_invalid_app_name_rejected(self, client):
        """App name that sanitizes to empty string is rejected."""
        r = client.post("/api/notify", json={
            "session_id": "sess-004",
            "app": "///...",
            "content": "hack",
        })
        assert r.status_code == 400
        assert "Invalid app name" in r.json()["detail"]

    def test_write_path_traversal_app_sanitized(self, client, sessions_dir):
        """Path traversal chars are stripped — file is created with safe name."""
        r = client.post("/api/notify", json={
            "session_id": "sess-005",
            "app": "../../etc",
            "content": "sanitized",
        })
        assert r.status_code == 200
        # The traversal chars are stripped, so the file is 'etc.md'
        f = sessions_dir / "sess-005" / "core" / "apps" / "etc.md"
        assert f.exists()
        assert f.read_text() == "sanitized"

    def test_write_path_traversal_session_rejected(self, client):
        r = client.post("/api/notify", json={
            "session_id": "../../../etc",
            "app": "test",
            "content": "hack",
        })
        assert r.status_code == 400
        assert "Invalid session_id" in r.json()["detail"]


# ── GET /api/notify/{session_id} ─────────────────────────────────────

class TestGetNotifications:
    def test_empty_session_returns_empty_list(self, client):
        r = client.get("/api/notify/nonexistent-session")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == "nonexistent-session"
        assert data["notifications"] == []

    def test_lists_posted_notifications(self, client):
        client.post("/api/notify", json={
            "session_id": "sess-010",
            "app": "alpha",
            "content": "AAA",
        })
        client.post("/api/notify", json={
            "session_id": "sess-010",
            "app": "beta",
            "content": "BBB",
        })
        r = client.get("/api/notify/sess-010")
        assert r.status_code == 200
        data = r.json()
        assert len(data["notifications"]) == 2
        apps = [n["app"] for n in data["notifications"]]
        assert "alpha" in apps
        assert "beta" in apps

    def test_notification_content_matches(self, client):
        client.post("/api/notify", json={
            "session_id": "sess-011",
            "app": "memo",
            "content": "Remember this!",
        })
        r = client.get("/api/notify/sess-011")
        notifs = r.json()["notifications"]
        assert len(notifs) == 1
        assert notifs[0]["content"] == "Remember this!"
        assert notifs[0]["chars"] == len("Remember this!")

    def test_get_path_traversal_rejected(self, client):
        r = client.get("/api/notify/../../../etc")
        # FastAPI may return 400 or 422 depending on routing
        assert r.status_code in (400, 404, 422)
