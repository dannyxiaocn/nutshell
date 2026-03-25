"""Tests for spawn_session tool and session_factory."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from nutshell.runtime.session_factory import init_session


# ── session_factory.init_session ──────────────────────────────────────────────

def test_init_session_creates_directory_structure(tmp_path):
    init_session(
        session_id="test-session",
        entity_name="nonexistent-entity",  # graceful fallback when entity missing
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
        entity_base=tmp_path / "entity",
    )

    session_dir = tmp_path / "sessions" / "test-session"
    system_dir = tmp_path / "_sessions" / "test-session"

    assert (session_dir / "core").is_dir()
    assert (session_dir / "core" / "tools").is_dir()
    assert (session_dir / "core" / "skills").is_dir()
    assert (session_dir / "docs").is_dir()
    assert (session_dir / "playground").is_dir()
    assert (system_dir / "manifest.json").exists()
    assert (system_dir / "context.jsonl").exists()
    assert (system_dir / "events.jsonl").exists()


def test_init_session_writes_manifest(tmp_path):
    init_session(
        session_id="my-session",
        entity_name="agent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
    )

    manifest = json.loads(
        (tmp_path / "_sessions" / "my-session" / "manifest.json").read_text()
    )
    assert manifest["session_id"] == "my-session"
    assert manifest["entity"] == "agent"
    assert "created_at" in manifest


def test_init_session_writes_initial_message(tmp_path):
    init_session(
        session_id="chat-session",
        entity_name="agent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
        initial_message="Hello, please do X",
    )

    ctx = tmp_path / "_sessions" / "chat-session" / "context.jsonl"
    events = [json.loads(l) for l in ctx.read_text().splitlines() if l.strip()]
    assert len(events) == 1
    assert events[0]["type"] == "user_input"
    assert events[0]["content"] == "Hello, please do X"
    assert "id" in events[0]


def test_init_session_no_initial_message_empty_context(tmp_path):
    init_session(
        session_id="quiet-session",
        entity_name="agent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
    )

    ctx = tmp_path / "_sessions" / "quiet-session" / "context.jsonl"
    assert ctx.read_text().strip() == ""


def test_init_session_idempotent(tmp_path):
    kwargs = dict(
        session_id="idem-session",
        entity_name="agent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
    )
    init_session(**kwargs)
    init_session(**kwargs)  # second call should not raise or overwrite core files

    session_dir = tmp_path / "sessions" / "idem-session"
    assert (session_dir / "core").is_dir()


# ── spawn_session tool ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spawn_session_creates_session(tmp_path):
    from nutshell.tool_engine.providers.spawn_session import spawn_session

    result = await spawn_session(
        entity="agent",
        _sessions_base=tmp_path / "sessions",
        _system_sessions_base=tmp_path / "_sessions",
        _entity_base=tmp_path / "entity",
    )

    assert "created" in result.lower() or "session" in result.lower()
    # At least one session directory should exist
    sessions = list((tmp_path / "_sessions").iterdir())
    assert len(sessions) == 1
    assert (sessions[0] / "manifest.json").exists()


@pytest.mark.asyncio
async def test_spawn_session_with_initial_message(tmp_path):
    from nutshell.tool_engine.providers.spawn_session import spawn_session

    await spawn_session(
        entity="agent",
        initial_message="Start the analysis",
        _sessions_base=tmp_path / "sessions",
        _system_sessions_base=tmp_path / "_sessions",
        _entity_base=tmp_path / "entity",
    )

    sessions = list((tmp_path / "_sessions").iterdir())
    ctx = sessions[0] / "context.jsonl"
    events = [json.loads(l) for l in ctx.read_text().splitlines() if l.strip()]
    assert any(e["content"] == "Start the analysis" for e in events)


# ── registry integration ──────────────────────────────────────────────────────

def test_spawn_session_registered_as_builtin():
    from nutshell.tool_engine.registry import get_builtin
    impl = get_builtin("spawn_session")
    assert impl is not None
    assert callable(impl)


# ── entity memory/ directory seeding ─────────────────────────────────────────

def test_init_session_copies_entity_memory_directory(tmp_path):
    """Entity memory/*.md files are copied to session core/memory/."""
    entity_dir = tmp_path / "entity" / "test-ent"
    mem_dir = entity_dir / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "layer_a.md").write_text("Alpha layer", encoding="utf-8")
    (mem_dir / "layer_b.md").write_text("Beta layer", encoding="utf-8")
    # Non-.md files should be ignored
    (mem_dir / "notes.txt").write_text("should not be copied", encoding="utf-8")

    init_session(
        session_id="mem-dir-session",
        entity_name="test-ent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
        entity_base=tmp_path / "entity",
    )

    session_mem = tmp_path / "sessions" / "mem-dir-session" / "core" / "memory"
    assert session_mem.is_dir()
    assert (session_mem / "layer_a.md").read_text(encoding="utf-8") == "Alpha layer"
    assert (session_mem / "layer_b.md").read_text(encoding="utf-8") == "Beta layer"
    assert not (session_mem / "notes.txt").exists()


def test_init_session_memory_directory_idempotent(tmp_path):
    """Second init_session call does not overwrite existing memory layer files."""
    entity_dir = tmp_path / "entity" / "test-ent"
    mem_dir = entity_dir / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "config.md").write_text("original from entity", encoding="utf-8")

    kwargs = dict(
        session_id="idem-mem-session",
        entity_name="test-ent",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
        entity_base=tmp_path / "entity",
    )
    init_session(**kwargs)

    # Agent modifies the file in session
    session_file = tmp_path / "sessions" / "idem-mem-session" / "core" / "memory" / "config.md"
    session_file.write_text("agent modified this", encoding="utf-8")

    # Second init should NOT overwrite
    init_session(**kwargs)
    assert session_file.read_text(encoding="utf-8") == "agent modified this"


def test_init_session_no_entity_memory_dir_no_error(tmp_path):
    """When entity has no memory/ directory, no error and no core/memory/ created."""
    init_session(
        session_id="no-mem-dir-session",
        entity_name="nonexistent-entity",
        sessions_base=tmp_path / "sessions",
        system_sessions_base=tmp_path / "_sessions",
        entity_base=tmp_path / "entity",
    )

    session_mem = tmp_path / "sessions" / "no-mem-dir-session" / "core" / "memory"
    # memory/ dir should NOT be created if entity has no memory/ dir
    assert not session_mem.exists()
