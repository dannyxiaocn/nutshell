"""QjbQ FastAPI server — notification relay for nutshell agents.

Endpoints:
    POST /api/notify           — write an app notification to a session
    GET  /api/notify/{session_id} — list all app notifications for a session
    GET  /health               — health check
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from cli_app.qjbq import __version__

# ── Sessions directory ───────────────────────────────────────────────
# Default: <repo_root>/sessions/  — overridable via QJBQ_SESSIONS_DIR
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SESSIONS_DIR = _REPO_ROOT / "sessions"


def _sessions_dir() -> Path:
    env = os.environ.get("QJBQ_SESSIONS_DIR")
    if env:
        return Path(env)
    return _DEFAULT_SESSIONS_DIR


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(title="QjbQ", version=__version__)


# ── Models ───────────────────────────────────────────────────────────
class NotifyRequest(BaseModel):
    session_id: str
    app: str
    content: str

    @field_validator("session_id", "app", "content")
    @classmethod
    def not_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return v.strip()


class NotifyResponse(BaseModel):
    ok: bool
    path: str
    chars: int


class NotificationItem(BaseModel):
    app: str
    content: str
    chars: int


class NotifyListResponse(BaseModel):
    session_id: str
    notifications: list[NotificationItem]


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Helpers ──────────────────────────────────────────────────────────
def _sanitize_app(name: str) -> str:
    """Allow only alphanumeric, dash, underscore."""
    return "".join(c for c in name if c.isalnum() or c in "-_")


def _validate_session_id(session_id: str) -> str:
    """Reject path-traversal attempts."""
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    if safe != session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    return safe


# ── Endpoints ────────────────────────────────────────────────────────
@app.post("/api/notify", response_model=NotifyResponse)
async def post_notify(req: NotifyRequest) -> NotifyResponse:
    """Write an app notification to a session's core/apps/<app>.md."""
    session_id = _validate_session_id(req.session_id)
    safe_app = _sanitize_app(req.app)
    if not safe_app:
        raise HTTPException(status_code=400, detail="Invalid app name")

    apps_dir = _sessions_dir() / session_id / "core" / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)

    target = apps_dir / f"{safe_app}.md"
    target.write_text(req.content, encoding="utf-8")

    rel_path = f"sessions/{session_id}/core/apps/{safe_app}.md"
    return NotifyResponse(ok=True, path=rel_path, chars=len(req.content))


@app.get("/api/notify/{session_id}", response_model=NotifyListResponse)
async def get_notifications(session_id: str) -> NotifyListResponse:
    """List all app notifications for a session."""
    session_id = _validate_session_id(session_id)
    apps_dir = _sessions_dir() / session_id / "core" / "apps"

    notifications: list[NotificationItem] = []
    if apps_dir.is_dir():
        for f in sorted(apps_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            notifications.append(
                NotificationItem(app=f.stem, content=content, chars=len(content))
            )

    return NotifyListResponse(session_id=session_id, notifications=notifications)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check."""
    return HealthResponse(status="ok", version=__version__)
