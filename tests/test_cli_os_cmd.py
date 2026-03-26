"""Tests for the ``nutshell os`` CLI subcommand."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from ui.cli.main import (
    cmd_os,
    _find_recent_cli_os_session,
    _CLI_OS_ENTITY,
    _CLI_OS_MAX_AGE_HOURS,
)

_INIT_SESSION_PATH = "nutshell.runtime.session_factory.init_session"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_session(tmp_path: Path, session_id: str, entity: str = "agent") -> tuple[Path, Path]:
    """Minimal session scaffold for testing (sessions + _sessions dirs)."""
    sessions = tmp_path / "sessions"
    system = tmp_path / "_sessions"
    s_dir = sessions / session_id / "core"
    sys_dir = system / session_id
    s_dir.mkdir(parents=True, exist_ok=True)
    sys_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "session_id": session_id,
        "entity": entity,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (sys_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (sys_dir / "status.json").write_text("{}", encoding="utf-8")
    (sys_dir / "context.jsonl").touch()
    (s_dir / "tasks.md").write_text("", encoding="utf-8")
    return sessions, system


def _make_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    defaults = dict(
        message=None,
        force_new=False,
        no_wait=True,
        timeout=5.0,
        sessions_base=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestConstants:
    def test_cli_os_entity_name(self):
        assert _CLI_OS_ENTITY == "cli_os"

    def test_max_age_hours_positive(self):
        assert _CLI_OS_MAX_AGE_HOURS > 0


# ── _find_recent_cli_os_session ───────────────────────────────────────────────

class TestFindRecentSession:
    def test_no_sessions_returns_none(self, tmp_path):
        sessions = tmp_path / "sessions"
        system = tmp_path / "_sessions"
        sessions.mkdir()
        system.mkdir()
        result = _find_recent_cli_os_session(sessions, system)
        assert result is None

    def test_finds_recent_cli_os_session(self, tmp_path):
        sessions, system = _seed_session(tmp_path, "os-session", entity="cli_os")
        result = _find_recent_cli_os_session(sessions, system)
        assert result == "os-session"

    def test_ignores_non_cli_os_entity(self, tmp_path):
        sessions, system = _seed_session(tmp_path, "agent-session", entity="agent")
        result = _find_recent_cli_os_session(sessions, system)
        assert result is None

    def test_ignores_stopped_session(self, tmp_path):
        sessions, system = _seed_session(tmp_path, "stopped-os", entity="cli_os")
        status_path = tmp_path / "_sessions" / "stopped-os" / "status.json"
        status_path.write_text(json.dumps({"status": "stopped"}))
        result = _find_recent_cli_os_session(sessions, system)
        assert result is None

    def test_ignores_old_session(self, tmp_path):
        sessions, system = _seed_session(tmp_path, "old-os", entity="cli_os")
        manifest = {
            "session_id": "old-os",
            "entity": "cli_os",
            "created_at": "2020-01-01T00:00:00+00:00",
        }
        (tmp_path / "_sessions" / "old-os" / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = _find_recent_cli_os_session(sessions, system)
        assert result is None


# ── cmd_os ────────────────────────────────────────────────────────────────────

class TestCmdOs:
    def test_creates_new_session(self, tmp_path, capsys):
        """With --new, cmd_os creates a new cli_os session."""
        args = _make_args(tmp_path, message="hello", force_new=True)
        with mock.patch(_INIT_SESSION_PATH) as m_init:
            m_init.return_value = "new-id"
            code = cmd_os(args)
        assert code == 0
        out = capsys.readouterr().out
        assert "CLI-OS session:" in out
        m_init.assert_called_once()
        _, kwargs = m_init.call_args
        assert kwargs["entity_name"] == "cli_os"

    def test_resumes_recent_session(self, tmp_path, capsys):
        """When a recent cli_os session exists, cmd_os continues it."""
        sessions, system = _seed_session(tmp_path, "recent-os", entity="cli_os")
        ctx = system / "recent-os" / "context.jsonl"
        ctx.touch()

        args = _make_args(tmp_path, message="hey")
        with mock.patch("ui.cli.chat._continue_session", return_value=0) as m_cont:
            code = cmd_os(args)
        assert code == 0
        out = capsys.readouterr().out
        assert "Resuming" in out
        assert "recent-os" in out
        m_cont.assert_called_once()

    def test_force_new_ignores_recent(self, tmp_path, capsys):
        """--new flag forces creation even when recent session exists."""
        _seed_session(tmp_path, "recent-os", entity="cli_os")
        args = _make_args(tmp_path, message="fresh start", force_new=True)
        with mock.patch(_INIT_SESSION_PATH) as m_init:
            m_init.return_value = "new-id"
            code = cmd_os(args)
        assert code == 0
        out = capsys.readouterr().out
        assert "CLI-OS session:" in out
        assert "Resuming" not in out

    def test_default_message_when_none(self, tmp_path, capsys):
        """When no message is given, a default greeting is used."""
        args = _make_args(tmp_path, message=None, force_new=True)
        with mock.patch(_INIT_SESSION_PATH) as m_init:
            m_init.return_value = "x"
            code = cmd_os(args)
        assert code == 0
        _, kwargs = m_init.call_args
        init_msg = kwargs.get("initial_message", "")
        assert len(init_msg) > 5  # non-trivial default message

    def test_entity_not_found(self, tmp_path, capsys):
        """If cli_os entity dir doesn't exist, returns error."""
        args = _make_args(tmp_path, force_new=True)
        with mock.patch("ui.cli.main._REPO_ROOT", tmp_path):
            code = cmd_os(args)
        assert code == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "cli_os" in err

    def test_init_session_failure(self, tmp_path, capsys):
        """If init_session raises, cmd_os returns 1 with error message."""
        args = _make_args(tmp_path, force_new=True, message="go")
        with mock.patch(_INIT_SESSION_PATH, side_effect=RuntimeError("boom")):
            code = cmd_os(args)
        assert code == 1
        err = capsys.readouterr().err
        assert "boom" in err
