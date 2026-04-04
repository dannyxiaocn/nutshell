"""Git Coordinator — master/sub role assignment for multi-agent git workflows.

When multiple agent sessions work on the same git repository, one session
is elected "master" (coordinates pushes, rebases) and the others are "subs".

Registry: _sessions/git_masters.json
    {
        "<git_remote_origin_url>": {
            "session_id": "...",
            "registered_at": "..."
        }
    }

The master is the first session to register for a given remote URL.
Subsequent sessions become subs. When a session stops, it releases its
master claim (if it held one).
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

_DEFAULT_SYSTEM_BASE = Path(__file__).parent.parent.parent / "_sessions"

Role = Literal["master", "sub"]


class GitCoordinator:
    """Coordinate git master/sub roles across agent sessions.

    Args:
        system_base: Path to _sessions/ directory containing git_masters.json.
    """

    def __init__(self, system_base: Path | None = None) -> None:
        self._system_base = system_base or _DEFAULT_SYSTEM_BASE
        self._registry_path = self._system_base / "git_masters.json"

    def _load_registry(self) -> dict:
        """Load the registry file, returning empty dict if missing/corrupt."""
        if not self._registry_path.exists():
            return {}
        try:
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_registry(self, registry: dict) -> None:
        """Atomically write the registry file."""
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._registry_path)

    @staticmethod
    def get_remote_url(repo_path: Path) -> str | None:
        """Get the git remote origin URL for a repo, or None if not available."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_session_alive(self, session_id: str) -> bool:
        """Check if a session is still running (has a PID in status.json)."""
        status_path = self._system_base / session_id / "status.json"
        if not status_path.exists():
            return False
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            pid = status.get("pid")
            if pid is None:
                return False
            # Check if PID is actually running
            os.kill(pid, 0)
            return True
        except (json.JSONDecodeError, OSError, ProcessLookupError, PermissionError):
            return False

    def register(self, repo_path: Path, session_id: str | None = None) -> Role:
        """Register a session for a git repo and return its role.

        If no session currently holds master for this repo's remote, the
        caller becomes master. Otherwise, it becomes a sub.

        Args:
            repo_path: Path to the git repository.
            session_id: Session ID (defaults to NUTSHELL_SESSION_ID env var).

        Returns:
            "master" or "sub".
        """
        session_id = session_id or os.environ.get("NUTSHELL_SESSION_ID", "")
        if not session_id:
            return "sub"

        remote_url = self.get_remote_url(repo_path)
        if not remote_url:
            # No remote — treat as local-only, always master
            return "master"

        registry = self._load_registry()
        entry = registry.get(remote_url)

        if entry is not None:
            if entry.get("session_id") == session_id:
                # Already registered as master
                return "master"
            # Another session is master — check if it's still alive
            if self._is_session_alive(entry.get("session_id", "")):
                return "sub"
            # Stale master — reclaim

        registry[remote_url] = {
            "session_id": session_id,
            "registered_at": datetime.now().isoformat(),
        }
        self._save_registry(registry)
        return "master"

    def release(self, session_id: str | None = None) -> list[str]:
        """Release all master claims held by a session.

        Args:
            session_id: Session to release (defaults to NUTSHELL_SESSION_ID).

        Returns:
            List of remote URLs that were released.
        """
        session_id = session_id or os.environ.get("NUTSHELL_SESSION_ID", "")
        if not session_id:
            return []

        registry = self._load_registry()
        released: list[str] = []
        to_remove: list[str] = []

        for url, entry in registry.items():
            if entry.get("session_id") == session_id:
                to_remove.append(url)
                released.append(url)

        if to_remove:
            for url in to_remove:
                del registry[url]
            self._save_registry(registry)

        return released

    def get_role(self, repo_path: Path, session_id: str | None = None) -> Role:
        """Check the current role without registering.

        Returns "master" if the session holds master for this repo, else "sub".
        """
        session_id = session_id or os.environ.get("NUTSHELL_SESSION_ID", "")
        remote_url = self.get_remote_url(repo_path)
        if not remote_url:
            return "master"

        registry = self._load_registry()
        entry = registry.get(remote_url)
        if entry and entry.get("session_id") == session_id:
            return "master"
        return "sub"

    def get_master(self, repo_path: Path) -> str | None:
        """Return the session_id of the current master for a repo, or None."""
        remote_url = self.get_remote_url(repo_path)
        if not remote_url:
            return None
        registry = self._load_registry()
        entry = registry.get(remote_url)
        if entry:
            return entry.get("session_id")
        return None
