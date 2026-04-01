"""Tests for nutshell.runtime.dream — session cleanup dream mechanism."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from nutshell.runtime.dream import (
    DreamReport,
    SessionInfo,
    _classify_session,
    _delete_session,
    _dir_size_mb,
    _discover_sessions,
    _get_dream_config,
    _update_meta_memory,
    run_dream,
    should_dream,
    dream_all,
)


def _make_session(
    tmp_path: Path,
    session_id: str,
    entity: str = "agent",
    status: str = "active",
    created_at: str | None = None,
    tasks: str = "",
    context_bytes: int = 0,
    playground_files: dict[str, str] | None = None,
    stopped_at: str | None = None,
) -> None:
    """Create a minimal session structure for testing."""
    s_base = tmp_path / "sessions"
    sys_base = tmp_path / "_sessions"

    session_dir = s_base / session_id
    system_dir = sys_base / session_id
    core_dir = session_dir / "core"

    core_dir.mkdir(parents=True, exist_ok=True)
    system_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "playground").mkdir(exist_ok=True)

    if created_at is None:
        created_at = datetime.now().isoformat()

    # Manifest
    manifest = {
        "session_id": session_id,
        "entity": entity,
        "created_at": created_at,
    }
    (system_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    # Status
    status_data = {"status": status, "updated_at": datetime.now().isoformat()}
    if stopped_at:
        status_data["stopped_at"] = stopped_at
    (system_dir / "status.json").write_text(
        json.dumps(status_data), encoding="utf-8"
    )

    # Context
    ctx = system_dir / "context.jsonl"
    if context_bytes > 0:
        ctx.write_bytes(b"x" * context_bytes)
    else:
        ctx.touch()

    # Tasks
    (core_dir / "tasks.md").write_text(tasks, encoding="utf-8")

    # Playground files
    if playground_files:
        for fname, content in playground_files.items():
            fpath = session_dir / "playground" / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")


def _make_meta(tmp_path: Path, entity: str = "agent") -> Path:
    """Create a minimal meta session structure."""
    meta_dir = tmp_path / "sessions" / f"{entity}_meta"
    (meta_dir / "core" / "memory").mkdir(parents=True, exist_ok=True)
    (meta_dir / "playground").mkdir(parents=True, exist_ok=True)
    return meta_dir


# ── Classification Tests ──────────────────────────────────────────────────────


class TestClassifySession:
    def test_active_recent_is_keep_active(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="active",
            created_at=(now - timedelta(hours=1)).isoformat(),
            last_activity=now.isoformat(),
            context_bytes=100,
            task_summary="",
        )
        assert _classify_session(info, now, force=False) == "keep_active"

    def test_active_with_tasks_is_keep_tracked(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="active",
            created_at=(now - timedelta(hours=5)).isoformat(),
            last_activity=(now - timedelta(hours=3)).isoformat(),
            context_bytes=100,
            task_summary="- [ ] do something",
        )
        assert _classify_session(info, now, force=False) == "keep_tracked"

    def test_stopped_with_tasks_is_keep_tracked(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="stopped",
            created_at=(now - timedelta(hours=1)).isoformat(),
            last_activity=(now - timedelta(hours=1)).isoformat(),
            context_bytes=100,
            task_summary="- [ ] pending task",
        )
        assert _classify_session(info, now, force=False) == "keep_tracked"

    def test_alignment_blocked(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="alignment_blocked",
            created_at=now.isoformat(),
            last_activity=now.isoformat(),
            context_bytes=0,
            task_summary="",
        )
        assert _classify_session(info, now, force=False) == "alignment_blocked"

    def test_stopped_with_context_is_archive(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="stopped",
            created_at=(now - timedelta(hours=10)).isoformat(),
            last_activity=(now - timedelta(hours=10)).isoformat(),
            context_bytes=500,
            task_summary="",
        )
        assert _classify_session(info, now, force=False) == "archive"

    def test_stopped_no_context_is_delete(self):
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="stopped",
            created_at=(now - timedelta(hours=100)).isoformat(),
            last_activity=(now - timedelta(hours=100)).isoformat(),
            context_bytes=0,
            task_summary="",
        )
        assert _classify_session(info, now, force=False) == "delete"

    def test_active_no_recent_no_tasks_is_keep_active(self):
        """Active sessions without recent activity and no tasks still kept."""
        now = datetime.now()
        info = SessionInfo(
            session_id="s1",
            entity="agent",
            status="active",
            created_at=(now - timedelta(hours=10)).isoformat(),
            last_activity=(now - timedelta(hours=5)).isoformat(),
            context_bytes=100,
            task_summary="",
        )
        assert _classify_session(info, now, force=False) == "keep_active"


# ── Integration Tests ─────────────────────────────────────────────────────────


class TestDreamDeletesOldStoppedSessions:
    def test_dream_deletes_old_stopped_sessions(self, tmp_path):
        """Stopped sessions with no tasks and no context are deleted."""
        _make_meta(tmp_path)
        old_time = (datetime.now() - timedelta(hours=72)).isoformat()
        _make_session(
            tmp_path,
            "old-stopped",
            status="stopped",
            created_at=old_time,
            context_bytes=0,
        )

        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        assert "old-stopped" in report.deleted
        assert not (tmp_path / "sessions" / "old-stopped").exists()
        assert not (tmp_path / "_sessions" / "old-stopped").exists()


class TestDreamKeepsTrackedSessionsWithTasks:
    def test_dream_keeps_tracked_sessions_with_tasks(self, tmp_path):
        """Sessions with non-empty tasks.md are kept and tracked."""
        _make_meta(tmp_path)
        _make_session(
            tmp_path,
            "has-tasks",
            status="stopped",
            tasks="- [ ] finish the report\n- [ ] review PR",
            context_bytes=100,
        )

        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        assert "has-tasks" in report.kept
        assert (tmp_path / "sessions" / "has-tasks").exists()
        assert (tmp_path / "_sessions" / "has-tasks").exists()


class TestDreamDryRunMakesNoChanges:
    def test_dream_dry_run_makes_no_changes(self, tmp_path):
        """Dry run classifies but doesn't delete anything."""
        _make_meta(tmp_path)
        _make_session(
            tmp_path,
            "to-delete",
            status="stopped",
            context_bytes=0,
        )
        _make_session(
            tmp_path,
            "to-archive",
            status="stopped",
            context_bytes=500,
        )

        report = run_dream(
            "agent",
            dry_run=True,
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        # Sessions classified but NOT deleted
        assert "to-delete" in report.deleted
        assert "to-archive" in report.archived
        assert (tmp_path / "sessions" / "to-delete").exists()
        assert (tmp_path / "sessions" / "to-archive").exists()
        assert (tmp_path / "_sessions" / "to-delete").exists()
        assert (tmp_path / "_sessions" / "to-archive").exists()


class TestDreamUpdatesMetaMemory:
    def test_dream_updates_meta_memory(self, tmp_path):
        """Dream writes dream_sessions.md and dream_log.md."""
        _make_meta(tmp_path)
        _make_session(
            tmp_path,
            "active-session",
            status="active",
            tasks="- [ ] important work",
            context_bytes=100,
        )
        _make_session(
            tmp_path,
            "dead-session",
            status="stopped",
            context_bytes=0,
        )

        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        memory_dir = tmp_path / "sessions" / "agent_meta" / "core" / "memory"
        sessions_md = memory_dir / "dream_sessions.md"
        log_md = memory_dir / "dream_log.md"

        assert sessions_md.exists()
        assert log_md.exists()

        sessions_content = sessions_md.read_text(encoding="utf-8")
        assert "active-session" in sessions_content
        assert "Active / Tracked" in sessions_content

        log_content = log_md.read_text(encoding="utf-8")
        assert "Dream" in log_content
        assert "Reviewed: 2" in log_content


class TestDreamStorageCalc:
    def test_dream_storage_calc(self, tmp_path):
        """Dream correctly calculates freed space and storage metrics."""
        _make_meta(tmp_path)
        # Create a session with some playground data
        _make_session(
            tmp_path,
            "big-session",
            status="stopped",
            context_bytes=0,
            playground_files={"data.txt": "x" * 10000},
        )

        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        assert "big-session" in report.deleted
        assert report.freed_mb > 0
        assert report.meta_playground_mb >= 0
        assert report.total_sessions_mb >= 0


class TestDreamCooldown:
    def test_dream_respects_cooldown(self, tmp_path):
        """Dream skips if called too recently (unless forced)."""
        meta_dir = _make_meta(tmp_path)
        last_dream_file = meta_dir / "core" / ".last_dream"
        last_dream_file.write_text(str(time.time()), encoding="utf-8")

        _make_session(tmp_path, "s1", status="stopped", context_bytes=0)

        # Without force, should be skipped
        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=False,
        )
        assert len(report.warnings) > 0
        assert "Skipped" in report.warnings[0]
        # Session should still exist
        assert (tmp_path / "sessions" / "s1").exists()

    def test_dream_force_ignores_cooldown(self, tmp_path):
        """Force flag skips cooldown check."""
        meta_dir = _make_meta(tmp_path)
        last_dream_file = meta_dir / "core" / ".last_dream"
        last_dream_file.write_text(str(time.time()), encoding="utf-8")

        _make_session(tmp_path, "s1", status="stopped", context_bytes=0)

        report = run_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )
        assert "s1" in report.deleted


class TestDreamConfig:
    def test_default_config(self, tmp_path):
        config = _get_dream_config("agent", tmp_path / "entity")
        assert config["max_sessions"] == 50
        assert config["dream_threshold"] == 30
        assert config["dream_interval"] == 21600

    def test_config_from_yaml(self, tmp_path):
        entity_dir = tmp_path / "entity" / "agent"
        entity_dir.mkdir(parents=True)
        (entity_dir / "agent.yaml").write_text(
            "name: agent\ndream:\n  max_sessions: 20\n  dream_threshold: 10\n",
            encoding="utf-8",
        )
        config = _get_dream_config("agent", tmp_path / "entity")
        assert config["max_sessions"] == 20
        assert config["dream_threshold"] == 10
        assert config["dream_interval"] == 21600  # default


class TestShouldDream:
    def test_under_threshold(self, tmp_path):
        """Should not dream when session count is under threshold."""
        _make_meta(tmp_path)
        _make_session(tmp_path, "s1")
        assert not should_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
        )

    def test_over_threshold(self, tmp_path):
        """Should dream when session count exceeds threshold."""
        entity_dir = tmp_path / "entity" / "agent"
        entity_dir.mkdir(parents=True)
        (entity_dir / "agent.yaml").write_text(
            "name: agent\ndream:\n  dream_threshold: 3\n",
            encoding="utf-8",
        )
        _make_meta(tmp_path)
        for i in range(5):
            _make_session(tmp_path, f"s{i}")

        assert should_dream(
            "agent",
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
        )


class TestDreamAll:
    def test_dream_all_multiple_entities(self, tmp_path):
        """dream_all processes all entities."""
        _make_meta(tmp_path, "agent")
        _make_meta(tmp_path, "kimi")
        _make_session(tmp_path, "a1", entity="agent", status="stopped", context_bytes=0)
        _make_session(tmp_path, "k1", entity="kimi", status="stopped", context_bytes=0)

        reports = dream_all(
            s_base=tmp_path / "sessions",
            sys_base=tmp_path / "_sessions",
            entity_base=tmp_path / "entity",
            force=True,
        )

        assert len(reports) == 2
        entities = {r.entity for r in reports}
        assert entities == {"agent", "kimi"}


class TestDirSizeMb:
    def test_nonexistent_dir(self, tmp_path):
        assert _dir_size_mb(tmp_path / "nope") == 0.0

    def test_dir_with_files(self, tmp_path):
        d = tmp_path / "testdir"
        d.mkdir()
        (d / "file.txt").write_bytes(b"x" * 1024)
        size = _dir_size_mb(d)
        assert 0 < size < 0.01  # ~0.001 MB


class TestDeleteSession:
    def test_delete_removes_both_dirs(self, tmp_path):
        _make_session(tmp_path, "doomed", status="stopped", context_bytes=100)
        freed = _delete_session(
            "doomed",
            tmp_path / "sessions",
            tmp_path / "_sessions",
            dry_run=False,
        )
        assert freed > 0
        assert not (tmp_path / "sessions" / "doomed").exists()
        assert not (tmp_path / "_sessions" / "doomed").exists()

    def test_delete_skips_active(self, tmp_path):
        _make_session(tmp_path, "running", status="active", context_bytes=100)
        freed = _delete_session(
            "running",
            tmp_path / "sessions",
            tmp_path / "_sessions",
            dry_run=False,
        )
        assert freed == 0
        assert (tmp_path / "sessions" / "running").exists()

    def test_dry_run_preserves(self, tmp_path):
        _make_session(tmp_path, "keep-me", status="stopped", context_bytes=100)
        freed = _delete_session(
            "keep-me",
            tmp_path / "sessions",
            tmp_path / "_sessions",
            dry_run=True,
        )
        assert freed > 0
        assert (tmp_path / "sessions" / "keep-me").exists()


class TestDiscoverSessions:
    def test_discovers_only_matching_entity(self, tmp_path):
        _make_session(tmp_path, "mine", entity="agent")
        _make_session(tmp_path, "theirs", entity="kimi")

        sessions = _discover_sessions(
            "agent", tmp_path / "sessions", tmp_path / "_sessions"
        )
        assert len(sessions) == 1
        assert sessions[0].session_id == "mine"

    def test_skips_meta_sessions(self, tmp_path):
        _make_meta(tmp_path, "agent")
        _make_session(tmp_path, "real", entity="agent")

        sessions = _discover_sessions(
            "agent", tmp_path / "sessions", tmp_path / "_sessions"
        )
        ids = [s.session_id for s in sessions]
        assert "real" in ids
        assert "agent_meta" not in ids

    def test_reads_task_summary(self, tmp_path):
        _make_session(
            tmp_path, "with-tasks", entity="agent",
            tasks="- [ ] first task\n- [ ] second task",
        )
        sessions = _discover_sessions(
            "agent", tmp_path / "sessions", tmp_path / "_sessions"
        )
        assert sessions[0].task_summary == "- [ ] first task; - [ ] second task"
