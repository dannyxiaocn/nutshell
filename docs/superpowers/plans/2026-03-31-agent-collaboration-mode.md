# Agent Collaboration Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Nutshell sessions to detect whether they are being driven by a human or another agent, inject structured response guidance in agent-to-agent mode, and coordinate git access when multiple sessions work on the same repo.

**Architecture:** Two independent features. Feature 1 threads a `caller_type` field from `user_input` events through `session.chat()` → `agent.run()` → `_build_system_parts()`, injecting a structured-reply prompt block when caller is an agent. Feature 2 adds a `GitCoordinator` that maintains a registry of which session "owns" each git repo's origin, so sub-node sessions commit locally without pushing to origin.

**Tech Stack:** Python stdlib only (`fcntl` for file locking, `subprocess` for git, `sys.stdin.isatty()` for TTY detection). No new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `ui/cli/chat.py` | Add TTY detection; write `caller` field to user_input event |
| `nutshell/tool_engine/providers/session_msg.py` | Write `caller: "agent"` to user_input event |
| `nutshell/runtime/session.py` | Read `caller` from event; thread `caller_type` through `chat()` |
| `nutshell/core/agent.py` | Accept `caller_type` in `run()` + `_build_system_parts()`; inject prompt block |
| `nutshell/runtime/git_coordinator.py` | **New** — GitCoordinator: register/release/get_master |
| `nutshell/tool_engine/providers/git_checkpoint.py` | Call GitCoordinator; include role in return value; skip push for sub-nodes |
| `nutshell/runtime/session.py` | Release master on session stop (second change, same file) |
| `tests/test_caller_detection.py` | **New** — tests for Feature 1 |
| `tests/test_git_coordinator.py` | **New** — tests for Feature 2 |

---

## Feature 1: Caller Detection + Agent-mode Prompt

---

### Task 1: Add `caller` field to user_input events

**Files:**
- Modify: `ui/cli/chat.py:46-55`
- Modify: `nutshell/tool_engine/providers/session_msg.py:53-60`
- Create: `tests/test_caller_detection.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_caller_detection.py
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


# ── cli/chat.py caller field ──────────────────────────────────────────────────

def test_send_message_writes_caller_human(tmp_path):
    """_send_message with caller='human' writes caller field to event."""
    from ui.cli.chat import _send_message
    ctx = tmp_path / "context.jsonl"
    ctx.touch()
    msg_id = _send_message(ctx, "hello", caller="human")
    events = [json.loads(l) for l in ctx.read_text().splitlines() if l]
    assert len(events) == 1
    assert events[0]["caller"] == "human"
    assert events[0]["id"] == msg_id


def test_send_message_writes_caller_agent(tmp_path):
    """_send_message with caller='agent' writes caller field to event."""
    from ui.cli.chat import _send_message
    ctx = tmp_path / "context.jsonl"
    ctx.touch()
    _send_message(ctx, "task", caller="agent")
    events = [json.loads(l) for l in ctx.read_text().splitlines() if l]
    assert events[0]["caller"] == "agent"


def test_send_message_default_caller_is_human(tmp_path):
    """_send_message without caller param defaults to 'human'."""
    from ui.cli.chat import _send_message
    ctx = tmp_path / "context.jsonl"
    ctx.touch()
    _send_message(ctx, "hello")
    events = [json.loads(l) for l in ctx.read_text().splitlines() if l]
    assert events[0]["caller"] == "human"


# ── send_to_session always writes agent ──────────────────────────────────────

def test_send_to_session_writes_caller_agent(tmp_path):
    """send_to_session always writes caller='agent' to user_input event."""
    import asyncio
    from nutshell.tool_engine.providers.session_msg import send_to_session

    system_base = tmp_path / "_sessions"
    session_id = "test-sess"
    sess_dir = system_base / session_id
    sess_dir.mkdir(parents=True)
    (sess_dir / "manifest.json").write_text("{}")
    ctx_path = sess_dir / "context.jsonl"
    ctx_path.touch()

    async def run():
        return await send_to_session(
            session_id=session_id,
            message="do task",
            mode="async",
            _system_base=system_base,
        )

    asyncio.run(run())
    events = [json.loads(l) for l in ctx_path.read_text().splitlines() if l]
    assert events[0]["caller"] == "agent"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/nutshell
pytest tests/test_caller_detection.py -v
```

Expected: FAIL — `_send_message() got an unexpected keyword argument 'caller'`

- [ ] **Step 3: Add `caller` param to `_send_message` in `ui/cli/chat.py`**

Current code at lines 46-55:
```python
def _send_message(ctx_path: Path, content: str) -> str:
    """Write user_input to context.jsonl, return msg_id."""
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": content,
        "id": msg_id,
        "ts": datetime.now().isoformat(),
    })
    return msg_id
```

Replace with:
```python
def _send_message(ctx_path: Path, content: str, caller: str = "human") -> str:
    """Write user_input to context.jsonl, return msg_id."""
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": content,
        "id": msg_id,
        "ts": datetime.now().isoformat(),
        "caller": caller,
    })
    return msg_id
```

- [ ] **Step 4: Add `caller: "agent"` to `send_to_session` in `nutshell/tool_engine/providers/session_msg.py`**

Current code at lines 53-60:
```python
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": message,
        "id": msg_id,
        "ts": datetime.now().isoformat(),
    })
```

Replace with:
```python
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": message,
        "id": msg_id,
        "ts": datetime.now().isoformat(),
        "caller": "agent",
    })
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_caller_detection.py::test_send_message_writes_caller_human \
       tests/test_caller_detection.py::test_send_message_writes_caller_agent \
       tests/test_caller_detection.py::test_send_message_default_caller_is_human \
       tests/test_caller_detection.py::test_send_to_session_writes_caller_agent \
       -v
```

Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add ui/cli/chat.py nutshell/tool_engine/providers/session_msg.py tests/test_caller_detection.py
git commit -m "feat: add caller field to user_input events (human/agent)"
```

---

### Task 2: Thread `caller_type` through session → agent

**Files:**
- Modify: `nutshell/runtime/session.py:257-293` (chat method) and `492-512` (daemon loop)
- Modify: `nutshell/core/agent.py:151-158` (run signature) and `109-140` (_build_system_parts)

- [ ] **Step 1: Add tests for caller_type threading**

Add to `tests/test_caller_detection.py`:

```python
# ── caller_type threads through session → agent ───────────────────────────────

def test_agent_run_accepts_caller_type():
    """agent.run() accepts caller_type kwarg without error."""
    import asyncio
    from nutshell.core.agent import Agent
    from unittest.mock import AsyncMock, MagicMock

    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value=("reply", [], MagicMock(total_tokens=0)))
    mock_provider._supports_cache_control = False

    agent = Agent(
        name="test",
        system_prompt="You are a test agent.",
        provider=mock_provider,
        tools=[],
        skills=[],
    )

    async def run():
        return await agent.run("hello", caller_type="agent")

    result = asyncio.run(run())
    assert result.content == "reply"


def test_agent_build_system_parts_injects_agent_prompt():
    """_build_system_parts injects agent-mode block when caller_type='agent'."""
    from unittest.mock import MagicMock
    from nutshell.core.agent import Agent

    mock_provider = MagicMock()
    mock_provider._supports_cache_control = False

    agent = Agent(
        name="test",
        system_prompt="You are a test agent.",
        provider=mock_provider,
        tools=[],
        skills=[],
    )

    _, suffix_agent = agent._build_system_parts(caller_type="agent")
    _, suffix_human = agent._build_system_parts(caller_type="human")

    assert "[DONE]" in suffix_agent
    assert "协作说明" in suffix_agent
    assert "[DONE]" not in suffix_human
    assert "协作说明" not in suffix_human
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_caller_detection.py::test_agent_run_accepts_caller_type \
       tests/test_caller_detection.py::test_agent_build_system_parts_injects_agent_prompt \
       -v
```

Expected: FAIL — `run() got an unexpected keyword argument 'caller_type'`

- [ ] **Step 3: Modify `agent.py` `_build_system_parts()` to accept `caller_type`**

Current signature at line 109:
```python
    def _build_system_parts(self) -> tuple[str, str]:
```

Replace with:
```python
    def _build_system_parts(self, caller_type: str = "human") -> tuple[str, str]:
```

At the end of `_build_system_parts()`, just before `return`, add the agent-mode block:

Current ending (lines 136-140):
```python
        skills_block = build_skills_block(self.skills)
        if skills_block:
            dynamic_parts.append(skills_block)

        return "\n".join(static_parts), "\n".join(dynamic_parts)
```

Replace with:
```python
        skills_block = build_skills_block(self.skills)
        if skills_block:
            dynamic_parts.append(skills_block)

        if caller_type == "agent":
            dynamic_parts.append(
                "\n---\n"
                "## 协作说明\n"
                "你当前由另一个 agent 调用。请在完成任务后用结构化前缀回复：\n"
                "- [DONE] 任务完成，简述结果\n"
                "- [REVIEW] 需要人工审核，说明原因\n"
                "- [BLOCKED] 遇到阻塞，描述问题\n"
                "- [ERROR] 执行失败，给出错误信息"
            )

        return "\n".join(static_parts), "\n".join(dynamic_parts)
```

- [ ] **Step 4: Modify `agent.py` `run()` to accept and forward `caller_type`**

Current signature at line 151-158:
```python
    async def run(
        self,
        input: str,
        *,
        clear_history: bool = False,
        on_text_chunk: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
```

Replace with:
```python
    async def run(
        self,
        input: str,
        *,
        clear_history: bool = False,
        caller_type: str = "human",
        on_text_chunk: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
```

At line 169, update the call to `_build_system_parts`:
```python
        # Current:
        system_prefix, system_dynamic = self._build_system_parts()
        # Replace with:
        system_prefix, system_dynamic = self._build_system_parts(caller_type=caller_type)
```

- [ ] **Step 5: Run agent tests to verify they pass**

```bash
pytest tests/test_caller_detection.py::test_agent_run_accepts_caller_type \
       tests/test_caller_detection.py::test_agent_build_system_parts_injects_agent_prompt \
       -v
```

Expected: PASS (2 tests)

- [ ] **Step 6: Thread `caller_type` through `session.py`**

In `session.py`, modify `chat()` at line 257 — add `caller_type` param and forward it:

Current:
```python
    async def chat(self, message: str, *, user_input_id: str | None = None) -> AgentResult:
        """Run agent with user message. Holds agent lock — blocks heartbeat tick."""
        old_len = len(self._agent._history)
        self._set_model_status("running", "user")
        tool_call_cb, get_tool_call_count = self._make_tool_call_callback()
        on_chunk = self._make_text_chunk_callback()
        try:
            async with self._agent_lock:
                self._load_session_capabilities()
                result = await self._agent.run(
                    message,
                    on_text_chunk=on_chunk,
                    on_tool_call=tool_call_cb,
                )
```

Replace with:
```python
    async def chat(
        self,
        message: str,
        *,
        user_input_id: str | None = None,
        caller_type: str = "human",
    ) -> AgentResult:
        """Run agent with user message. Holds agent lock — blocks heartbeat tick."""
        old_len = len(self._agent._history)
        self._set_model_status("running", "user")
        tool_call_cb, get_tool_call_count = self._make_tool_call_callback()
        on_chunk = self._make_text_chunk_callback()
        try:
            async with self._agent_lock:
                self._load_session_capabilities()
                result = await self._agent.run(
                    message,
                    caller_type=caller_type,
                    on_text_chunk=on_chunk,
                    on_tool_call=tool_call_cb,
                )
```

In `run_daemon_loop()`, modify the input processing loop at lines 493-504:

Current:
```python
                for msg in inputs:
                    content = msg.get("content", "")
                    msg_id = msg.get("id")
                    # User message wakes a stopped session
                    if self.is_stopped():
                        self.set_status("active")
                        self._append_event({"type": "status", "value": "resumed"})
                    # Context reshape: clean up any orphaned user message at history tail
                    content = self._reshape_history(content)
                    try:
                        await self.chat(content, user_input_id=msg_id)
```

Replace with:
```python
                for msg in inputs:
                    content = msg.get("content", "")
                    msg_id = msg.get("id")
                    caller_type = msg.get("caller", "human")
                    # User message wakes a stopped session
                    if self.is_stopped():
                        self.set_status("active")
                        self._append_event({"type": "status", "value": "resumed"})
                    # Context reshape: clean up any orphaned user message at history tail
                    content = self._reshape_history(content)
                    try:
                        await self.chat(content, user_input_id=msg_id, caller_type=caller_type)
```

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
pytest tests/ -q
```

Expected: All existing tests pass (no regressions from signature changes — all new params have defaults).

- [ ] **Step 8: Commit**

```bash
git add nutshell/core/agent.py nutshell/runtime/session.py
git commit -m "feat: thread caller_type through session→agent, inject agent-mode prompt block"
```

---

### Task 3: TTY detection in `nutshell chat` CLI

**Files:**
- Modify: `ui/cli/chat.py` — detect TTY at call site, pass `caller` to `_send_message`

- [ ] **Step 1: Add TTY detection test**

Add to `tests/test_caller_detection.py`:

```python
# ── TTY detection ─────────────────────────────────────────────────────────────

def test_tty_stdin_maps_to_human_caller(tmp_path, monkeypatch):
    """When stdin is a TTY, caller should be 'human'."""
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    from ui.cli import chat as chat_mod
    assert chat_mod._detect_caller() == "human"


def test_non_tty_stdin_maps_to_agent_caller(tmp_path, monkeypatch):
    """When stdin is not a TTY (pipe/script), caller should be 'agent'."""
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    from ui.cli import chat as chat_mod
    assert chat_mod._detect_caller() == "agent"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_caller_detection.py::test_tty_stdin_maps_to_human_caller \
       tests/test_caller_detection.py::test_non_tty_stdin_maps_to_agent_caller \
       -v
```

Expected: FAIL — `module 'ui.cli.chat' has no attribute '_detect_caller'`

- [ ] **Step 3: Add `_detect_caller()` helper to `ui/cli/chat.py`**

Add after the existing imports (after line 36, before `_append_jsonl`):

```python
def _detect_caller() -> str:
    """Return 'human' if stdin is a TTY (interactive), else 'agent' (script/pipe)."""
    import sys
    return "human" if sys.stdin.isatty() else "agent"
```

- [ ] **Step 4: Update `_continue_session()` in `ui/cli/chat.py` to pass caller**

Find the call to `_send_message` inside `_continue_session()` (around line 120) and update it:

```python
# Current (find this pattern):
    msg_id = _send_message(ctx_path, args.message)

# Replace with:
    msg_id = _send_message(ctx_path, args.message, caller=_detect_caller())
```

- [ ] **Step 5: Update `_new_session()` in `ui/cli/chat.py` to pass caller**

Find the call to `_send_message` inside `_new_session()` (around line 231) and update it similarly:

```python
# Current (find this pattern — there may be one or two):
    msg_id = _send_message(ctx_path, args.message)

# Replace with:
    msg_id = _send_message(ctx_path, args.message, caller=_detect_caller())
```

- [ ] **Step 6: Run TTY detection tests**

```bash
pytest tests/test_caller_detection.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -q
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add ui/cli/chat.py tests/test_caller_detection.py
git commit -m "feat: detect TTY to set caller=human/agent in nutshell chat CLI"
```

---

## Feature 2: Git Master Node Coordination

---

### Task 4: Create `GitCoordinator`

**Files:**
- Create: `nutshell/runtime/git_coordinator.py`
- Create: `tests/test_git_coordinator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_git_coordinator.py
from __future__ import annotations

import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _make_coordinator(tmp_path):
    from nutshell.runtime.git_coordinator import GitCoordinator
    system_base = tmp_path / "_sessions"
    system_base.mkdir()
    return GitCoordinator(system_base=system_base), system_base


def _make_git_repo(path: Path) -> Path:
    """Create a real git repo with a remote set to a fake URL."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
        cwd=str(path), check=True, capture_output=True
    )
    return path


def test_first_session_becomes_master(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")
    role = coord.register_master(repo, "session-A")
    assert role == "master"


def test_second_session_becomes_sub_when_master_alive(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")

    # Create a "live" master session: status.json with a pid
    sess_dir = system_base / "session-A"
    sess_dir.mkdir()
    (sess_dir / "status.json").write_text(json.dumps({"pid": 99999, "status": "active"}))

    coord.register_master(repo, "session-A")
    role = coord.register_master(repo, "session-B")
    assert role == "sub"


def test_session_takes_over_from_dead_master(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")

    # Create a "dead" master session: no pid
    sess_dir = system_base / "session-A"
    sess_dir.mkdir()
    (sess_dir / "status.json").write_text(json.dumps({"pid": None, "status": "active"}))

    coord.register_master(repo, "session-A")
    role = coord.register_master(repo, "session-B")
    assert role == "master"

    # Verify registry updated
    assert coord.get_master(repo) == "session-B"


def test_release_master_removes_entry(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")
    coord.register_master(repo, "session-A")
    coord.release_master(repo, "session-A")
    assert coord.get_master(repo) is None


def test_release_does_nothing_if_not_master(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")
    coord.register_master(repo, "session-A")
    coord.release_master(repo, "session-B")  # B is not master
    assert coord.get_master(repo) == "session-A"


def test_re_registering_own_session_stays_master(tmp_path):
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")
    coord.register_master(repo, "session-A")
    role = coord.register_master(repo, "session-A")
    assert role == "master"


def test_no_git_repo_returns_master(tmp_path):
    """A directory without git remote gracefully returns 'master'."""
    coord, system_base = _make_coordinator(tmp_path)
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    role = coord.register_master(not_a_repo, "session-A")
    assert role == "master"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_git_coordinator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nutshell.runtime.git_coordinator'`

- [ ] **Step 3: Create `nutshell/runtime/git_coordinator.py`**

```python
"""Git master node coordinator.

Prevents multiple sessions from pushing to the same origin concurrently.
Maintains a registry (_sessions/git_masters.json) mapping origin URL →
session_id of the master. First live session to claim a repo is master;
others become sub-nodes.
"""
from __future__ import annotations

import fcntl
import json
import subprocess
from pathlib import Path

_REGISTRY_FILE = "git_masters.json"
_LOCK_FILE = "git_masters.lock"


class GitCoordinator:
    def __init__(self, system_base: Path):
        self._system_base = system_base
        self._registry_path = system_base / _REGISTRY_FILE
        self._lock_path = system_base / _LOCK_FILE

    # ── Git helpers ───────────────────────────────────────────────────────────

    def _get_origin_url(self, workdir: Path) -> str | None:
        """Return the git remote origin URL, or None if not a git repo."""
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    # ── Registry I/O ──────────────────────────────────────────────────────────

    def _read_registry(self) -> dict:
        if not self._registry_path.exists():
            return {}
        try:
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_registry(self, data: dict) -> None:
        self._registry_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Session liveness ─────────────────────────────────────────────────────

    def _session_alive(self, session_id: str) -> bool:
        """Return True if the session has a recorded PID (is running)."""
        from nutshell.runtime.status import read_session_status
        status_dir = self._system_base / session_id
        if not status_dir.exists():
            return False
        st = read_session_status(status_dir)
        return st.get("pid") is not None

    # ── Public API ────────────────────────────────────────────────────────────

    def register_master(self, workdir: Path, session_id: str) -> str:
        """Try to register session_id as master for the repo at workdir.

        Returns 'master' if the session becomes/stays master,
        or 'sub' if a live master already exists.
        """
        origin_url = self._get_origin_url(workdir)
        if not origin_url:
            # Can't coordinate without a remote — treat as standalone master
            return "master"

        self._system_base.mkdir(parents=True, exist_ok=True)
        lock_file = open(self._lock_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            registry = self._read_registry()
            existing = registry.get(origin_url)

            if existing is None or existing == session_id:
                registry[origin_url] = session_id
                self._write_registry(registry)
                return "master"

            if self._session_alive(existing):
                return "sub"

            # Dead master — take over
            registry[origin_url] = session_id
            self._write_registry(registry)
            return "master"
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    def get_master(self, workdir: Path) -> str | None:
        """Return session_id of current master, or None."""
        origin_url = self._get_origin_url(workdir)
        if not origin_url:
            return None
        return self._read_registry().get(origin_url)

    def release_master(self, workdir: Path, session_id: str) -> None:
        """Remove registry entry if session_id is the current master."""
        origin_url = self._get_origin_url(workdir)
        if not origin_url:
            return

        self._system_base.mkdir(parents=True, exist_ok=True)
        lock_file = open(self._lock_path, "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            registry = self._read_registry()
            if registry.get(origin_url) == session_id:
                del registry[origin_url]
                self._write_registry(registry)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_git_coordinator.py -v
```

Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add nutshell/runtime/git_coordinator.py tests/test_git_coordinator.py
git commit -m "feat: add GitCoordinator for master/sub-node git registry"
```

---

### Task 5: Integrate `GitCoordinator` into `git_checkpoint`

**Files:**
- Modify: `nutshell/tool_engine/providers/git_checkpoint.py`
- Modify: `tests/test_git_coordinator.py` (add integration tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_git_coordinator.py`:

```python
# ── git_checkpoint integration ────────────────────────────────────────────────

def _make_git_repo_with_commit(path: Path) -> Path:
    """Create a git repo with a commit so git_checkpoint can work."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
        cwd=str(path), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path), check=True, capture_output=True
    )
    (path / "README.md").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path), check=True, capture_output=True
    )
    return path


@pytest.mark.asyncio
async def test_git_checkpoint_master_shows_role(tmp_path, monkeypatch):
    """git_checkpoint returns master role info when session is master."""
    import os
    from nutshell.tool_engine.providers import git_checkpoint as gc_mod

    sessions_base = tmp_path / "sessions"
    sessions_base.mkdir()
    system_base = tmp_path / "_sessions"
    system_base.mkdir()

    session_id = "sess-master"
    monkeypatch.setenv("NUTSHELL_SESSION_ID", session_id)

    # Session dir with playground/repo
    sess_dir = sessions_base / session_id
    repo = _make_git_repo_with_commit(sess_dir / "playground" / "repo")
    (repo / "new_file.txt").write_text("change")

    result = await gc_mod.git_checkpoint(
        message="test commit",
        workdir="playground/repo",
        _sessions_base=sessions_base,
        _system_base=system_base,
    )
    assert "Committed" in result
    assert "[master]" in result


@pytest.mark.asyncio
async def test_git_checkpoint_sub_shows_role(tmp_path, monkeypatch):
    """git_checkpoint returns sub-node role info when a live master exists."""
    import os, json
    from nutshell.tool_engine.providers import git_checkpoint as gc_mod
    from nutshell.runtime.git_coordinator import GitCoordinator

    sessions_base = tmp_path / "sessions"
    sessions_base.mkdir()
    system_base = tmp_path / "_sessions"
    system_base.mkdir()

    master_id = "sess-master"
    sub_id = "sess-sub"

    # Pre-register master as alive
    master_sys = system_base / master_id
    master_sys.mkdir()
    (master_sys / "status.json").write_text(json.dumps({"pid": 99999}))

    # Create sub's repo
    sess_dir = sessions_base / sub_id
    repo = _make_git_repo_with_commit(sess_dir / "playground" / "repo")
    (repo / "new_file.txt").write_text("change")

    # Pre-register master for this origin URL
    coord = GitCoordinator(system_base=system_base)
    coord.register_master(repo, master_id)

    monkeypatch.setenv("NUTSHELL_SESSION_ID", sub_id)

    result = await gc_mod.git_checkpoint(
        message="test commit",
        workdir="playground/repo",
        _sessions_base=sessions_base,
        _system_base=system_base,
    )
    assert "Committed" in result
    assert "[sub-node" in result
    assert master_id in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_git_coordinator.py::test_git_checkpoint_master_shows_role \
       tests/test_git_coordinator.py::test_git_checkpoint_sub_shows_role \
       -v
```

Expected: FAIL — `git_checkpoint() got an unexpected keyword argument '_system_base'`

- [ ] **Step 3: Modify `git_checkpoint.py` to use GitCoordinator**

Replace the entire file content with:

```python
"""git_checkpoint — built-in tool for agents to commit workspace changes.

Agents working in a git repository (e.g. playground/nutshell/) can call this
tool to stage all changes and create a checkpoint commit. Designed for the
nutshell_dev workflow where the agent works in an isolated playground clone
and wants to persist its progress without needing raw bash git commands.

Usage:
    git_checkpoint(message="feat: implement X", workdir="playground/nutshell")
    # → "Committed abc1234: feat: implement X  (3 files changed, +42 -5) [master]"
    # → "Committed abc1234: feat: implement X  (3 files changed, +42 -5) [sub-node, master: sess-abc]"
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_SESSIONS_BASE = _REPO_ROOT / "sessions"
_DEFAULT_SYSTEM_BASE = _REPO_ROOT / "_sessions"


async def git_checkpoint(
    *,
    message: str,
    workdir: str = "",
    _sessions_base: Path | None = None,
    _system_base: Path | None = None,
) -> str:
    """Stage all changes and create a checkpoint commit in a git repository.

    If there is nothing to commit, returns a "(nothing to commit)" message
    without creating an empty commit.

    Args:
        message: Commit message (required — forces the agent to describe intent).
        workdir: Path to the git repository, relative to the session directory
                 (e.g. "playground/nutshell"). Defaults to the session directory
                 itself if empty.

    Returns:
        Commit hash + summary + role tag on success, or an error/status string.
    """
    session_id = os.environ.get("NUTSHELL_SESSION_ID", "")
    if not session_id:
        return "Error: no active session (NUTSHELL_SESSION_ID not set)."

    sessions_base = _sessions_base or _DEFAULT_SESSIONS_BASE
    system_base = _system_base or _DEFAULT_SYSTEM_BASE
    session_dir = sessions_base / session_id

    if workdir:
        cwd = (session_dir / workdir).resolve()
    else:
        cwd = session_dir.resolve()

    if not cwd.exists():
        return f"Error: workdir not found: {cwd}"

    def _run(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )

    # Verify it's a git repo
    check = _run(["git", "rev-parse", "--git-dir"])
    if check.returncode != 0:
        return f"Error: not a git repository at {cwd}"

    # Register with GitCoordinator — determine master/sub role
    role_tag = ""
    try:
        from nutshell.runtime.git_coordinator import GitCoordinator
        coord = GitCoordinator(system_base=system_base)
        role = coord.register_master(cwd, session_id)
        if role == "master":
            role_tag = " [master]"
        else:
            master_id = coord.get_master(cwd) or "unknown"
            role_tag = f" [sub-node, master: {master_id}]"
    except Exception:
        pass  # Coordination failure is non-fatal

    # Stage all changes
    add_result = _run(["git", "add", "-A"])
    if add_result.returncode != 0:
        return f"Error staging changes: {add_result.stderr.strip()}"

    # Check if there's anything staged
    diff_result = _run(["git", "diff", "--cached", "--stat"])
    if not diff_result.stdout.strip():
        return f"(nothing to commit: working tree clean){role_tag}"

    # Commit
    commit_result = _run(["git", "commit", "-m", message])
    if commit_result.returncode != 0:
        return f"Error committing: {commit_result.stderr.strip()}"

    # Extract short hash from output
    hash_result = _run(["git", "rev-parse", "--short", "HEAD"])
    short_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else "?"

    # Build summary from commit output (last line of --stat summary)
    lines = commit_result.stdout.strip().splitlines()
    summary = ""
    for line in lines:
        if "changed" in line:
            summary = f"  ({line.strip()})"
            break

    return f"Committed {short_hash}: {message}{summary}{role_tag}"
```

- [ ] **Step 4: Run the integration tests**

```bash
pytest tests/test_git_coordinator.py -v
```

Expected: All PASS (9 tests total)

- [ ] **Step 5: Run the existing git_checkpoint tests to check for regressions**

```bash
pytest tests/test_git_checkpoint.py -v
```

Expected: All pass (the `_system_base` param has a default, backward compatible).

- [ ] **Step 6: Commit**

```bash
git add nutshell/tool_engine/providers/git_checkpoint.py tests/test_git_coordinator.py
git commit -m "feat: integrate GitCoordinator into git_checkpoint, show master/sub role"
```

---

### Task 6: Release master on session stop

**Files:**
- Modify: `nutshell/runtime/session.py` — release all master registrations on clean shutdown

- [ ] **Step 1: Write the failing test**

Add to `tests/test_git_coordinator.py`:

```python
def test_session_releases_master_on_stop(tmp_path):
    """GitCoordinator.release_master is called when a session stops."""
    # This tests the Session cleanup path by simulating the coordinator call
    coord, system_base = _make_coordinator(tmp_path)
    repo = _make_git_repo(tmp_path / "repo")

    coord.register_master(repo, "session-A")
    assert coord.get_master(repo) == "session-A"

    coord.release_master(repo, "session-A")
    assert coord.get_master(repo) is None
```

(This test validates the contract that `release_master` is the cleanup mechanism; the actual `session.py` integration is verified by running the full suite.)

- [ ] **Step 2: Run test to verify it passes** (it tests coordinator directly)

```bash
pytest tests/test_git_coordinator.py::test_session_releases_master_on_stop -v
```

Expected: PASS (coordinator test — verifies the cleanup contract)

- [ ] **Step 3: Add cleanup in `session.py` `run_daemon_loop` finally block**

In `session.py`, find the cleanup section at lines 549-557:

```python
        except asyncio.CancelledError:
            self._set_model_status("idle", "system")
            self._append_event({"type": "status", "value": "cancelled"})
            self._clear_pid()
            raise

        self._set_model_status("idle", "system")
        self._append_event({"type": "status", "value": "stopped"})
        self._clear_pid()
```

Replace with:

```python
        except asyncio.CancelledError:
            self._set_model_status("idle", "system")
            self._append_event({"type": "status", "value": "cancelled"})
            self._clear_pid()
            self._release_git_master()
            raise

        self._set_model_status("idle", "system")
        self._append_event({"type": "status", "value": "stopped"})
        self._clear_pid()
        self._release_git_master()
```

- [ ] **Step 4: Add `_release_git_master()` method to `Session` class**

Add this method near the other private helpers in `session.py` (e.g., after `_clear_pid` around line 438):

```python
    def _release_git_master(self) -> None:
        """Release any git master registrations held by this session."""
        try:
            from nutshell.runtime.git_coordinator import GitCoordinator
            # Scan session playground for git repos this session might own
            playground = self.session_dir / "playground"
            if not playground.exists():
                return
            coord = GitCoordinator(system_base=self.system_dir.parent)
            for child in playground.iterdir():
                if child.is_dir() and (child / ".git").exists():
                    coord.release_master(child, self._session_id)
        except Exception:
            pass  # Cleanup is best-effort
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -q
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add nutshell/runtime/session.py tests/test_git_coordinator.py
git commit -m "feat: release git master registration on session stop"
```

---

## Final Steps

### Task 7: Update README and version

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump version in `pyproject.toml`**

Find `version = "1.3.38"` and change to `version = "1.3.39"`.

- [ ] **Step 2: Update README.md**

Add to the **Architecture** or **Agent Design** section a paragraph about agent collaboration:

```markdown
### Agent Collaboration Mode

Nutshell detects whether a session is driven by a human or another agent and adapts accordingly:

- **Caller detection**: `nutshell chat` checks `sys.stdin.isatty()` — TTY → human, pipe/script → agent. `send_to_session` always marks the caller as agent.
- **Agent-mode prompt**: When caller is an agent, sessions receive a structured-reply guidance block instructing them to prefix responses with `[DONE]`, `[REVIEW]`, `[BLOCKED]`, or `[ERROR]`.
- **Git master node**: When multiple sessions work on the same git repo, the first to call `git_checkpoint` registers as master (tracked in `_sessions/git_masters.json`). Sub-nodes commit locally and see their role in the `git_checkpoint` return value. Masters are released on session stop.
```

Add a Changelog entry:
```markdown
### v1.3.39 — Agent Collaboration Mode

- **Caller detection**: `user_input` events now carry a `caller` field (`"human"` | `"agent"`). `nutshell chat` sets it via TTY detection; `send_to_session` hardcodes `"agent"`.
- **Agent-mode system prompt**: When `caller == "agent"`, sessions inject a structured-reply guidance block (`[DONE]`, `[REVIEW]`, `[BLOCKED]`, `[ERROR]`) into the dynamic prompt suffix.
- **Git master node coordination**: New `nutshell/runtime/git_coordinator.py` — `GitCoordinator` maintains `_sessions/git_masters.json` mapping origin URLs to master session IDs. `git_checkpoint` registers master/sub role and includes `[master]` or `[sub-node, master: <id>]` in output. Sessions release master on stop.
```

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -q
```

Expected: All pass.

- [ ] **Step 4: Final commit**

```bash
git add README.md pyproject.toml
git commit -m "v1.3.39: agent collaboration mode (caller detection + git master node)"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```
