# CLI + Multi-agent Session Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `nutshell-chat` CLI (single-shot agent interaction) and `send_to_session` system tool (session-to-session messaging).

**Architecture:** All IPC goes through the existing `context.jsonl` file protocol. `send_message()` already returns `msg_id`; we add `user_input_id` to `turn` events so callers can match responses. `send_to_session` is a system tool like `web_search`. `nutshell-chat` is a thin CLI wrapper over the same IPC.

**Tech Stack:** Python stdlib only (pathlib, json, uuid, asyncio, argparse). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-24-cli-and-multiagent-design.md`

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `nutshell/runtime/session.py` | `chat()` takes `user_input_id`; daemon passes msg ID; `run_daemon_loop()` gets `stop_event` |
| Create | `nutshell/tool_engine/providers/session_msg.py` | `send_to_session` implementation |
| Modify | `nutshell/tool_engine/registry.py` | Register `send_to_session` in `_BUILTIN_FACTORIES` |
| Create | `entity/agent/tools/send_to_session.json` | Tool schema for agent entity |
| Create | `ui/cli/__init__.py` | Package marker |
| Create | `ui/cli/chat.py` | `nutshell-chat` CLI |
| Modify | `pyproject.toml` | Register `nutshell-chat` entry point |
| Modify | `tests/test_session_capabilities.py` | Verify turn contains `user_input_id` |
| Create | `tests/test_send_to_session.py` | sync/async/timeout/self-call tests |
| Create | `tests/test_cli_chat.py` | CLI new-session/continue/no-wait tests |

---

## Task 1: Add `user_input_id` to turn events

**Files:** Modify `nutshell/runtime/session.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_session_capabilities.py` (after existing tests):

```python
def test_chat_turn_includes_user_input_id(tmp_path):
    """chat() should tag the turn with the user_input_id it processed."""
    agent = Agent(system_prompt="You echo.", provider=MockProvider([("echo", [])]))
    session = make_session(tmp_path, agent)
    session._load_session_capabilities()
    ipc = FileIPC(session.system_dir)

    msg_id = ipc.send_message("hello")
    import asyncio
    asyncio.run(session.chat("hello", user_input_id=msg_id))

    # Read last turn from context.jsonl
    lines = session._context_path.read_text().strip().split("\n")
    turn = json.loads(lines[-1])
    assert turn["type"] == "turn"
    assert turn.get("user_input_id") == msg_id
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_session_capabilities.py::test_chat_turn_includes_user_input_id -v
```
Expected: `TypeError: chat() got an unexpected keyword argument 'user_input_id'`

- [ ] **Step 3: Implement**

In `nutshell/runtime/session.py`, change `chat()` signature and turn construction:

```python
async def chat(self, message: str, *, user_input_id: str | None = None) -> AgentResult:
```

In the turn dict (around line 259):
```python
turn: dict = {
    "type": "turn",
    "triggered_by": "user",
    "messages": self._serialize_turn_messages(result.messages[old_len:]),
}
if user_input_id:
    turn["user_input_id"] = user_input_id
```

Also update `run_daemon_loop` to pass the ID (around line 416):
```python
for msg in inputs:
    content = msg.get("content", "")
    msg_id = msg.get("id")          # ← capture ID
    if self.is_stopped():
        ...
    content = self._reshape_history(content)
    try:
        await self.chat(content, user_input_id=msg_id)   # ← pass ID
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_session_capabilities.py::test_chat_turn_includes_user_input_id -v
```

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -q
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git checkout -b feat/cli-and-multiagent
git add nutshell/runtime/session.py tests/test_session_capabilities.py
git commit -m "feat: add user_input_id to turn events for response matching"
```

---

## Task 2: Add `stop_event` to `run_daemon_loop`

**Files:** Modify `nutshell/runtime/session.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_session_capabilities.py`:

```python
def test_daemon_stops_when_stop_event_set(tmp_path):
    """run_daemon_loop should exit when stop_event is set."""
    import asyncio
    agent = Agent(system_prompt="s", provider=MockProvider([]))
    session = make_session(tmp_path, agent)
    ipc = FileIPC(session.system_dir)

    stop = asyncio.Event()

    async def _run():
        task = asyncio.create_task(session.run_daemon_loop(ipc, stop_event=stop))
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=2.0)

    asyncio.run(_run())  # Must complete without hanging
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_session_capabilities.py::test_daemon_stops_when_stop_event_set -v
```
Expected: `TypeError: run_daemon_loop() got an unexpected keyword argument 'stop_event'`

- [ ] **Step 3: Implement**

Change `run_daemon_loop` signature:
```python
async def run_daemon_loop(
    self,
    ipc: "FileIPC",
    stop_event: asyncio.Event | None = None,
) -> None:
```

In the `while True:` loop, add check at the bottom (just before `await asyncio.sleep(0.5)`):
```python
if stop_event is not None and stop_event.is_set():
    break
await asyncio.sleep(0.5)
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_session_capabilities.py::test_daemon_stops_when_stop_event_set -v
```

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add nutshell/runtime/session.py tests/test_session_capabilities.py
git commit -m "feat: add stop_event param to run_daemon_loop for clean CLI shutdown"
```

---

## Task 3: `send_to_session` tool

**Files:**
- Create `nutshell/tool_engine/providers/session_msg.py`
- Modify `nutshell/tool_engine/registry.py`
- Create `tests/test_send_to_session.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_send_to_session.py`:

```python
"""Tests for send_to_session built-in tool."""
import asyncio
import json
import time
import pytest
from pathlib import Path
from nutshell.tool_engine.providers.session_msg import send_to_session


def _make_fake_session(tmp_path: Path, session_id: str) -> Path:
    """Create minimal _sessions/<id>/ structure for testing."""
    system_dir = tmp_path / session_id
    system_dir.mkdir(parents=True)
    (system_dir / "manifest.json").write_text(
        json.dumps({"entity": "agent", "created_at": "2026-01-01"})
    )
    (system_dir / "context.jsonl").write_text("")
    return system_dir


@pytest.mark.asyncio
async def test_async_mode_writes_user_input_and_returns(tmp_path):
    sid = "test-session-async"
    system_dir = _make_fake_session(tmp_path, sid)

    result = await send_to_session(
        session_id=sid,
        message="hello",
        mode="async",
        _system_base=tmp_path,   # override default path for testing
    )

    assert "sent" in result.lower() or sid in result
    lines = (system_dir / "context.jsonl").read_text().strip().split("\n")
    events = [json.loads(l) for l in lines if l.strip()]
    assert any(e["type"] == "user_input" and e["content"] == "hello" for e in events)


@pytest.mark.asyncio
async def test_session_not_found_returns_error(tmp_path):
    result = await send_to_session(
        session_id="nonexistent",
        message="hello",
        _system_base=tmp_path,
    )
    assert "not found" in result.lower() or "error" in result.lower()


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
    assert "cannot" in result.lower() or "self" in result.lower()


@pytest.mark.asyncio
async def test_sync_mode_times_out_when_no_response(tmp_path):
    sid = "test-session-sync-timeout"
    _make_fake_session(tmp_path, sid)

    result = await send_to_session(
        session_id=sid,
        message="hello",
        mode="sync",
        timeout=0.5,   # very short timeout
        _system_base=tmp_path,
    )
    assert "timeout" in result.lower() or "timed out" in result.lower()


@pytest.mark.asyncio
async def test_sync_mode_returns_turn_content(tmp_path):
    """When a matching turn appears in context.jsonl, sync mode returns it."""
    import uuid
    sid = "test-session-sync-match"
    system_dir = _make_fake_session(tmp_path, sid)

    async def _write_turn_after_delay(ctx_path: Path, msg_id: str):
        await asyncio.sleep(0.1)
        turn = {
            "type": "turn",
            "triggered_by": "user",
            "user_input_id": msg_id,
            "messages": [{"role": "assistant", "content": "reply text"}],
            "ts": "2026-01-01T00:00:00",
        }
        with ctx_path.open("a") as f:
            f.write(json.dumps(turn) + "\n")

    # We need to know the msg_id ahead of time — use monkeypatching of uuid
    fixed_id = str(uuid.uuid4())

    import nutshell.tool_engine.providers.session_msg as sm
    original_uuid = sm.uuid

    class _FixedUUID:
        @staticmethod
        def uuid4():
            return type("U", (), {"__str__": lambda self: fixed_id})()

    sm.uuid = _FixedUUID()
    try:
        ctx_path = system_dir / "context.jsonl"
        writer = asyncio.create_task(_write_turn_after_delay(ctx_path, fixed_id))
        result = await send_to_session(
            session_id=sid,
            message="hello",
            mode="sync",
            timeout=2.0,
            _system_base=tmp_path,
        )
        await writer
    finally:
        sm.uuid = original_uuid

    assert result == "reply text"
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_send_to_session.py -v
```
Expected: `ModuleNotFoundError: No module named 'nutshell.tool_engine.providers.session_msg'`

- [ ] **Step 3: Implement `session_msg.py`**

Create `nutshell/tool_engine/providers/session_msg.py`:

```python
"""send_to_session built-in tool — session-to-session messaging via FileIPC."""
from __future__ import annotations

import asyncio
import json
import os
import uuid as _uuid_mod
from pathlib import Path
from typing import Any

# Allow import to be overridden in tests
uuid = _uuid_mod

_DEFAULT_SYSTEM_BASE = Path(__file__).parent.parent.parent.parent / "_sessions"


async def send_to_session(
    *,
    session_id: str,
    message: str,
    mode: str = "sync",
    timeout: float = 60.0,
    _system_base: Path | None = None,
) -> str:
    """Send a message to another Nutshell session.

    Args:
        session_id: Target session ID.
        message: Message content to send.
        mode: "sync" (wait for reply) or "async" (fire-and-forget).
        timeout: Max seconds to wait in sync mode.
        _system_base: Override _sessions/ directory (for testing).

    Returns:
        In sync mode: the agent's response text, or an error string.
        In async mode: confirmation string.
    """
    system_base = _system_base or _DEFAULT_SYSTEM_BASE
    target_dir = system_base / session_id

    # Self-call guard
    current_sid = os.environ.get("NUTSHELL_SESSION_ID", "")
    if current_sid and current_sid == session_id:
        return f"Error: cannot send to own session ({session_id})."

    # Existence check
    if not (target_dir / "manifest.json").exists():
        return f"Error: session '{session_id}' not found."

    ctx_path = target_dir / "context.jsonl"

    # Write user_input
    msg_id = str(uuid.uuid4())
    event = {"type": "user_input", "content": message, "id": msg_id,
             "ts": _now_iso()}
    _append_jsonl(ctx_path, event)

    if mode == "async":
        return f"Message sent to session {session_id}."

    # Sync: poll for matching turn
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        reply = _find_turn(ctx_path, msg_id)
        if reply is not None:
            return reply
        await asyncio.sleep(0.5)

    return f"Timeout: no response from session {session_id} within {timeout:.0f}s."


def _append_jsonl(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _find_turn(ctx_path: Path, msg_id: str) -> str | None:
    """Scan context.jsonl for a turn with user_input_id == msg_id.

    Returns the last assistant text if found, else None.
    """
    if not ctx_path.exists():
        return None
    try:
        with ctx_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "turn":
                    continue
                if event.get("user_input_id") != msg_id:
                    continue
                # Found matching turn — extract last assistant text
                for msg in reversed(event.get("messages", [])):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    return block.get("text", "")
                return ""
    except Exception:
        return None
    return None


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()
```

- [ ] **Step 4: Register in `registry.py`**

Add to `_BUILTIN_FACTORIES` in `nutshell/tool_engine/registry.py`:

```python
def _make_send_to_session() -> Callable:
    from nutshell.tool_engine.providers.session_msg import send_to_session
    return send_to_session


_BUILTIN_FACTORIES: dict[str, Callable[[], Callable]] = {
    "bash":            _make_bash,
    "web_search":      _make_web_search,
    "send_to_session": _make_send_to_session,
}
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_send_to_session.py -v
```
Expected: all pass (the sync-match test may need minor UUID patching adjustment).

- [ ] **Step 6: Create entity tool schema**

Create `entity/agent/tools/send_to_session.json`:

```json
{
  "name": "send_to_session",
  "description": "Send a message to another Nutshell session. mode=sync waits for the target agent's reply (blocks until response or timeout); mode=async fires-and-forgets. WARNING: avoid circular calls (A→B→A) — they will deadlock.",
  "input_schema": {
    "type": "object",
    "properties": {
      "session_id": {
        "type": "string",
        "description": "Target session ID (the ID shown when the session was created)."
      },
      "message": {
        "type": "string",
        "description": "The message content to send."
      },
      "mode": {
        "type": "string",
        "enum": ["sync", "async"],
        "description": "sync=wait for reply (default); async=fire-and-forget."
      },
      "timeout": {
        "type": "number",
        "description": "Seconds to wait in sync mode before giving up (default: 60)."
      }
    },
    "required": ["session_id", "message"]
  }
}
```

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add nutshell/tool_engine/providers/session_msg.py \
        nutshell/tool_engine/registry.py \
        entity/agent/tools/send_to_session.json \
        tests/test_send_to_session.py
git commit -m "feat: add send_to_session system tool for session-to-session messaging"
```

---

## Task 4: `nutshell-chat` CLI

**Files:**
- Create `ui/cli/__init__.py`
- Create `ui/cli/chat.py`
- Modify `pyproject.toml`
- Create `tests/test_cli_chat.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_chat.py`:

```python
"""Tests for nutshell-chat CLI."""
import asyncio
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


def _make_system_dir(tmp_path: Path, session_id: str) -> Path:
    sdir = tmp_path / "_sessions" / session_id
    sdir.mkdir(parents=True)
    (sdir / "manifest.json").write_text(json.dumps({"entity": "agent"}))
    (sdir / "context.jsonl").write_text("")
    (sdir / "status.json").write_text(json.dumps({"status": "active"}))
    (sdir / "events.jsonl").write_text("")
    return sdir


def test_continue_session_requires_existing_session(tmp_path, capsys):
    """--session with nonexistent ID should exit(1) with error message."""
    from ui.cli.chat import main
    with pytest.raises(SystemExit) as exc:
        with patch("sys.argv", ["nutshell-chat", "--session", "nonexistent", "--system-base", str(tmp_path / "_sessions"), "hi"]):
            main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()


def test_no_wait_continues_session_and_exits_zero(tmp_path, capsys):
    """--no-wait with valid session should write user_input and exit(0)."""
    sid = "my-session"
    sdir = _make_system_dir(tmp_path, sid)

    from ui.cli.chat import main
    with patch("sys.argv", [
        "nutshell-chat", "--session", sid,
        "--no-wait",
        "--system-base", str(tmp_path / "_sessions"),
        "hello there",
    ]):
        main()

    events = [json.loads(l) for l in (sdir / "context.jsonl").read_text().strip().split("\n") if l.strip()]
    assert any(e["type"] == "user_input" and e["content"] == "hello there" for e in events)
    captured = capsys.readouterr()
    assert captured.err == ""


def test_continue_session_reads_matching_turn(tmp_path, capsys):
    """--session should print agent response when matching turn appears."""
    import threading
    import time
    import uuid

    sid = "resp-session"
    sdir = _make_system_dir(tmp_path, sid)
    ctx_path = sdir / "context.jsonl"

    # We'll inject a matching turn after a short delay
    injected_msg_id: list[str] = []

    def _watch_and_respond():
        # Wait for user_input to appear, then write matching turn
        for _ in range(20):
            time.sleep(0.1)
            content = ctx_path.read_text()
            for line in content.splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("type") == "user_input":
                        mid = ev.get("id", "")
                        turn = {
                            "type": "turn",
                            "triggered_by": "user",
                            "user_input_id": mid,
                            "messages": [{"role": "assistant", "content": "test response"}],
                            "ts": "2026-01-01T00:00:00",
                        }
                        with ctx_path.open("a") as f:
                            f.write(json.dumps(turn) + "\n")
                        return
                except Exception:
                    pass

    t = threading.Thread(target=_watch_and_respond, daemon=True)
    t.start()

    from ui.cli.chat import main
    with patch("sys.argv", [
        "nutshell-chat", "--session", sid,
        "--system-base", str(tmp_path / "_sessions"),
        "--timeout", "5",
        "what is the answer?",
    ]):
        main()

    t.join(timeout=3)
    captured = capsys.readouterr()
    assert "test response" in captured.out
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/test_cli_chat.py -v
```
Expected: `ModuleNotFoundError: No module named 'ui.cli'`

- [ ] **Step 3: Create CLI package**

```bash
mkdir -p ui/cli
touch ui/cli/__init__.py
```

- [ ] **Step 4: Implement `ui/cli/chat.py`**

```python
"""nutshell-chat — single-shot CLI for interacting with a Nutshell session.

Usage:
    nutshell-chat "message"                             # new session
    nutshell-chat --entity kimi_agent "message"         # new session, custom entity
    nutshell-chat --session <id> "message"              # continue session
    nutshell-chat --session <id> --no-wait "message"    # fire-and-forget
    nutshell-chat --session <id> --timeout 60 "message" # custom timeout
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

_DEFAULT_SYSTEM_BASE = Path(__file__).parent.parent.parent / "_sessions"
_DEFAULT_SESSIONS_BASE = Path(__file__).parent.parent.parent / "sessions"
_POLL_INTERVAL = 0.5


def _now_iso() -> str:
    return datetime.now().isoformat()


def _append_jsonl(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_matching_turn(ctx_path: Path, msg_id: str) -> str | None:
    """Scan context.jsonl for a turn with user_input_id == msg_id."""
    if not ctx_path.exists():
        return None
    try:
        with ctx_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "turn":
                    continue
                if event.get("user_input_id") != msg_id:
                    continue
                for msg in reversed(event.get("messages", [])):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    return block.get("text", "")
                return ""
    except Exception:
        return None
    return None


def _wait_for_reply(ctx_path: Path, msg_id: str, timeout: float) -> str | None:
    """Poll context.jsonl until a matching turn appears or timeout."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        reply = _read_matching_turn(ctx_path, msg_id)
        if reply is not None:
            return reply
        time.sleep(_POLL_INTERVAL)
    return None


def _send_message(ctx_path: Path, content: str) -> str:
    """Write user_input to context.jsonl, return msg_id."""
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": content,
        "id": msg_id,
        "ts": _now_iso(),
    })
    return msg_id


def _continue_session(
    session_id: str,
    message: str,
    *,
    no_wait: bool,
    timeout: float,
    system_base: Path,
) -> int:
    """Handle --session <id> mode. Returns exit code."""
    system_dir = system_base / session_id
    if not (system_dir / "manifest.json").exists():
        print(f"Error: session '{session_id}' not found in {system_base}", file=sys.stderr)
        return 1

    ctx_path = system_dir / "context.jsonl"
    msg_id = _send_message(ctx_path, message)

    if no_wait:
        return 0

    reply = _wait_for_reply(ctx_path, msg_id, timeout)
    if reply is None:
        print(f"Error: no response within {timeout:.0f}s", file=sys.stderr)
        return 1

    print(reply)
    return 0


def _new_session(
    entity_name: str,
    message: str,
    *,
    no_wait: bool,
    timeout: float,
    system_base: Path,
    sessions_base: Path,
) -> int:
    """Handle new-session mode (no --session). Returns exit code."""
    import threading
    from nutshell.llm_engine.loader import AgentLoader
    from nutshell.runtime.session import Session
    from nutshell.runtime.ipc import FileIPC

    # Load agent from entity
    entity_base = Path(__file__).parent.parent.parent / "entity"
    try:
        agent = AgentLoader(entity_base).load(entity_name)
    except Exception as exc:
        print(f"Error: failed to load entity '{entity_name}': {exc}", file=sys.stderr)
        return 1

    session = Session(agent, base_dir=sessions_base, system_base=system_base)
    session_id = session._session_id
    ipc = FileIPC(session.system_dir)

    # Signal that daemon has recorded input_offset (so we write AFTER)
    ready_event = threading.Event()
    stop_event = asyncio.Event()  # will be set from main thread

    def _run_daemon():
        async def _async():
            # Tiny hack: set ready after context_size() is captured in run_daemon_loop.
            # We monkey-patch ipc.context_size to signal readiness on first call.
            original_ctx_size = ipc.context_size
            called = False

            def _patched_ctx_size():
                nonlocal called
                result = original_ctx_size()
                if not called:
                    called = True
                    ready_event.set()
                return result

            ipc.context_size = _patched_ctx_size
            await session.run_daemon_loop(ipc, stop_event=stop_event)

        asyncio.run(_async())

    daemon_thread = threading.Thread(target=_run_daemon, daemon=True)
    daemon_thread.start()

    # Wait for daemon to record input_offset before writing user_input
    if not ready_event.wait(timeout=5.0):
        print("Error: daemon failed to start", file=sys.stderr)
        return 1

    ctx_path = session.system_dir / "context.jsonl"
    msg_id = _send_message(ctx_path, message)

    # Always print Session ID (even in --no-wait mode)
    if no_wait:
        print(f"Session: {session_id}")
        stop_event.set()
        daemon_thread.join(timeout=3)
        return 0

    reply = _wait_for_reply(ctx_path, msg_id, timeout)

    stop_event.set()
    daemon_thread.join(timeout=3)

    if reply is None:
        print(f"Error: no response within {timeout:.0f}s", file=sys.stderr)
        print(f"Session: {session_id}")
        return 1

    print(reply)
    print(f"\nSession: {session_id}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nutshell-chat",
        description="Send a message to a Nutshell session and print the response.",
    )
    parser.add_argument("message", help="Message to send to the agent")
    parser.add_argument("--session", metavar="ID", help="Continue an existing session")
    parser.add_argument("--entity", default="agent", metavar="NAME",
                        help="Entity to use when creating a new session (default: agent)")
    parser.add_argument("--no-wait", action="store_true",
                        help="Send without waiting for a response")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="Seconds to wait for response (default: 120)")
    parser.add_argument("--system-base", type=Path, default=_DEFAULT_SYSTEM_BASE,
                        help=argparse.SUPPRESS)  # for testing
    parser.add_argument("--sessions-base", type=Path, default=_DEFAULT_SESSIONS_BASE,
                        help=argparse.SUPPRESS)  # for testing
    args = parser.parse_args()

    if args.session:
        code = _continue_session(
            args.session, args.message,
            no_wait=args.no_wait,
            timeout=args.timeout,
            system_base=args.system_base,
        )
    else:
        code = _new_session(
            args.entity, args.message,
            no_wait=args.no_wait,
            timeout=args.timeout,
            system_base=args.system_base,
            sessions_base=args.sessions_base,
        )

    sys.exit(code)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Register entry point in `pyproject.toml`**

Add to `[project.scripts]`:
```toml
nutshell-chat = "ui.cli.chat:main"
```

- [ ] **Step 6: Re-install in dev mode**

```bash
pip install -e . -q
```

- [ ] **Step 7: Run CLI tests**

```bash
pytest tests/test_cli_chat.py -v
```

- [ ] **Step 8: Run full suite**

```bash
pytest tests/ -q
```

- [ ] **Step 9: Smoke test**

```bash
# Quick smoke: should fail cleanly for nonexistent session
nutshell-chat --session nonexistent "hello"
echo "Exit code: $?"
```
Expected: error message on stderr, exit code 1.

- [ ] **Step 10: Commit**

```bash
git add ui/cli/ pyproject.toml tests/test_cli_chat.py
git commit -m "feat: add nutshell-chat CLI for single-shot session interaction"
```

---

## Task 5: Update logistics + set NUTSHELL_SESSION_ID in daemon

**Files:** `nutshell/runtime/session.py`, `pyproject.toml`, `README.md`

- [ ] **Step 1: Set NUTSHELL_SESSION_ID in daemon**

In `run_daemon_loop()`, after `self._ipc = ipc`:
```python
os.environ["NUTSHELL_SESSION_ID"] = self._session_id
```

This lets `send_to_session` detect self-calls.

- [ ] **Step 2: Update README**

Add section after "Quick Start":

```markdown
## CLI

```bash
# New session (prints response + Session ID)
nutshell-chat "Help me plan a data pipeline"

# Continue existing session
nutshell-chat --session 2026-03-24_10-00-00 "What's the status?"

# Different entity
nutshell-chat --entity kimi_agent "Review this code"

# Fire and forget (doesn't wait for response)
nutshell-chat --session <id> --no-wait "Run the overnight report"
```
```

- [ ] **Step 3: Bump version**

`pyproject.toml`: `1.1.8` → `1.1.9`
`README.md` heading: `v1.1.8` → `v1.1.9`

Add changelog entry:
```
### v1.1.9
- **`nutshell-chat` CLI** — single-shot agent interaction from terminal.
  `nutshell-chat "message"` creates a new session; `--session <id>` continues one.
  Always prints the agent response; new sessions also print `Session: <id>`.
  `--no-wait` for fire-and-forget. Supports `--timeout`, `--entity`.
- **`send_to_session` system tool** — agents can now message other sessions.
  `mode=sync` blocks until the target agent replies; `mode=async` fires and returns.
  Self-call is detected and rejected. Timeout returns a clear error string.
- **`user_input_id` in turn events** — `turn` events now carry `user_input_id`
  to unambiguously match a response to its triggering message (avoiding heartbeat
  turn confusion).
- **`stop_event` in `run_daemon_loop`** — clean shutdown for CLI and tests.
```

- [ ] **Step 4: Run full suite one final time**

```bash
pytest tests/ -q
```
Expected: all green.

- [ ] **Step 5: Commit and push**

```bash
git add -u
git commit -m "v1.1.9: nutshell-chat CLI + send_to_session tool"
git push origin feat/cli-and-multiagent
```

---

## Usage Log (post-implementation task)

After merging, use `nutshell-chat` with a kimi_agent session to execute further tasks. Maintain a usage log at `docs/usage-log.md`:

```markdown
# Nutshell Usage Log

## Entry format
- Date, session ID, entity used
- What worked / what didn't
- Missing features → TODO for implementation
```

Rule: if a desired feature doesn't exist in nutshell, add it to the log as a TODO and implement it — never work around it.
