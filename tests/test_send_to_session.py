"""Tests for send_to_session built-in tool."""
from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path

from nutshell.tool_engine.providers.session_msg import send_to_session, _find_turn


def _make_fake_session(tmp_path: Path, session_id: str) -> Path:
    """Create minimal _sessions/<id>/ structure."""
    system_dir = tmp_path / session_id
    system_dir.mkdir(parents=True)
    (system_dir / "manifest.json").write_text(
        json.dumps({"entity": "agent", "created_at": "2026-01-01"})
    )
    (system_dir / "context.jsonl").write_text("")
    return system_dir


# ── async mode ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_mode_writes_user_input_and_returns(tmp_path):
    sid = "test-async"
    system_dir = _make_fake_session(tmp_path, sid)

    result = await send_to_session(
        session_id=sid,
        message="hello async",
        mode="async",
        _system_base=tmp_path,
    )

    assert sid in result or "sent" in result.lower()
    lines = (system_dir / "context.jsonl").read_text().strip().split("\n")
    events = [json.loads(l) for l in lines if l.strip()]
    assert any(
        e.get("type") == "user_input" and e.get("content") == "hello async"
        for e in events
    )


# ── session not found ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_not_found_returns_error(tmp_path):
    result = await send_to_session(
        session_id="ghost-session",
        message="hello",
        _system_base=tmp_path,
    )
    assert "not found" in result.lower()


# ── self-call guard ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_self_call_returns_error(tmp_path, monkeypatch):
    sid = "self-session"
    _make_fake_session(tmp_path, sid)
    monkeypatch.setenv("NUTSHELL_SESSION_ID", sid)

    result = await send_to_session(
        session_id=sid,
        message="hi",
        _system_base=tmp_path,
    )
    assert "cannot" in result.lower() or "own" in result.lower()


# ── sync timeout ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_mode_times_out_when_no_response(tmp_path):
    sid = "timeout-session"
    _make_fake_session(tmp_path, sid)

    result = await send_to_session(
        session_id=sid,
        message="hello",
        mode="sync",
        timeout=0.3,
        _system_base=tmp_path,
    )
    assert "timeout" in result.lower() or "timed out" in result.lower()


# ── sync match ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_mode_returns_turn_content(tmp_path):
    """A matching turn written concurrently is returned in sync mode."""
    sid = "match-session"
    system_dir = _make_fake_session(tmp_path, sid)
    ctx_path = system_dir / "context.jsonl"

    async def _write_turn_when_ready():
        # Wait for user_input to appear, then write matching turn
        for _ in range(40):
            await asyncio.sleep(0.05)
            for line in ctx_path.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "user_input":
                    mid = ev.get("id", "")
                    turn = {
                        "type": "turn",
                        "triggered_by": "user",
                        "user_input_id": mid,
                        "messages": [{"role": "assistant", "content": "matched reply"}],
                        "ts": "2026-01-01T00:00:00",
                    }
                    with ctx_path.open("a") as f:
                        f.write(json.dumps(turn) + "\n")
                    return

    writer = asyncio.create_task(_write_turn_when_ready())
    result = await send_to_session(
        session_id=sid,
        message="query",
        mode="sync",
        timeout=5.0,
        _system_base=tmp_path,
    )
    await writer
    assert result == "matched reply"


# ── _find_turn helper ────────────────────────────────────────────────────────

def test_find_turn_returns_none_when_no_match(tmp_path):
    ctx = tmp_path / "context.jsonl"
    ctx.write_text(json.dumps({
        "type": "turn",
        "user_input_id": "other-id",
        "messages": [{"role": "assistant", "content": "nope"}],
    }) + "\n")
    assert _find_turn(ctx, "my-id") is None


def test_find_turn_returns_text_for_matching_id(tmp_path):
    ctx = tmp_path / "context.jsonl"
    ctx.write_text(json.dumps({
        "type": "turn",
        "user_input_id": "my-id",
        "messages": [{"role": "assistant", "content": "found it"}],
    }) + "\n")
    assert _find_turn(ctx, "my-id") == "found it"


def test_find_turn_handles_block_content(tmp_path):
    ctx = tmp_path / "context.jsonl"
    ctx.write_text(json.dumps({
        "type": "turn",
        "user_input_id": "block-id",
        "messages": [{"role": "assistant", "content": [
            {"type": "text", "text": "block text"},
        ]}],
    }) + "\n")
    assert _find_turn(ctx, "block-id") == "block text"


# ── registry integration ──────────────────────────────────────────────────────

def test_send_to_session_registered_as_builtin():
    from nutshell.tool_engine.registry import get_builtin
    impl = get_builtin("send_to_session")
    assert impl is not None
    assert callable(impl)
