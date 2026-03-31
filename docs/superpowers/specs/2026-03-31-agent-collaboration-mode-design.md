# Agent Collaboration Mode — Design Spec

**Date:** 2026-03-31  
**Status:** Approved

---

## Overview

Two related features to enable safe, coherent multi-agent collaboration in Nutshell:

1. **Caller Detection + Agent-mode System Prompt** — detect whether a session is being driven by a human or another agent, and inject structured response guidance when caller is an agent.
2. **Git Master Node Coordination** — when multiple sessions operate on the same git repo, elect a master session that owns origin I/O; sub-nodes sync from master to avoid conflicts.

---

## Feature 1: Caller Detection + Agent-mode Prompt

### Goal

When an agent calls a Nutshell session (via `nutshell chat` script/pipe or `send_to_session`), the receiving agent should know it is in agent-to-agent mode and respond with structured, parseable output. When a human is at the terminal, this guidance is suppressed.

### Detection Logic

| Invocation path | `caller` value |
|-----------------|---------------|
| `nutshell chat` with a TTY (`sys.stdin.isatty()`) | `"human"` |
| `nutshell chat` without a TTY (pipe / script) | `"agent"` |
| `send_to_session` tool | `"agent"` (hardcoded) |

### Data Flow

1. **`user_input` event** gains an optional `caller` field (default: `"human"` if absent — backward compatible).
2. **`ui/cli/chat.py` `_send_message()`** — detect TTY, write `caller` into event.
3. **`nutshell/tool_engine/providers/session_msg.py`** — always write `caller: "agent"`.
4. **`nutshell/runtime/session.py` `run_daemon_loop()`** — read `caller` from each `user_input` event, pass as `caller_type` kwarg to `session.chat()`.
5. **`nutshell/runtime/session.py` `chat()`** — pass `caller_type` down to `self._agent.run()`.
6. **`nutshell/core/agent.py` `run()`** — accept `caller_type: str = "human"`, pass to `_build_system_parts()`.
7. **`nutshell/core/agent.py` `_build_system_parts()`** — when `caller_type == "agent"`, append agent-mode block to dynamic suffix.

### Injected Prompt Block

Appended at the end of the dynamic suffix (after skills catalog):

```
---
## 协作说明
你当前由另一个 agent 调用。请在完成任务后用结构化前缀回复：
- [DONE] 任务完成，简述结果
- [REVIEW] 需要人工审核，说明原因
- [BLOCKED] 遇到阻塞，描述问题
- [ERROR] 执行失败，给出错误信息
```

### Backward Compatibility

- Old `user_input` events without `caller` field → treated as `"human"`.
- No changes to event schema versioning required.

---

## Feature 2: Git Master Node Coordination

### Goal

When multiple agent sessions clone/work on the same git repo in their playground directories, only one session (the "master") communicates with `origin`. Other sessions ("sub-nodes") pull from master's local copy, preventing push conflicts and keeping a single source of truth per repo.

### Registry

**File:** `_sessions/git_masters.json`

```json
{
  "https://github.com/org/repo.git": "session-id-of-master"
}
```

Registry key = **git remote origin URL** (obtained via `git remote get-url origin` in workdir). This is canonical across all sessions that clone the same repo, unlike local playground paths which differ per session.

- Guarded by a file lock (`_sessions/git_masters.lock`) to prevent race conditions.
- Written atomically (read → update → write under lock).

### Master Election

Triggered when a session first calls `git_checkpoint` for a given `workdir`:

1. Lock `git_masters.lock`.
2. Read `git_masters.json`.
3. Check if a master exists for this repo path:
   - **No master** → register self as master. Return `role: "master"`.
   - **Master exists, session alive** (status != stopped) → become sub-node. Return `role: "sub"`.
   - **Master exists, session dead** → take over as master, update registry. Return `role: "master"`.
4. Unlock.

Session liveness check: read `_sessions/<session_id>/status.json`, check `status` field.

### Master Behavior

- Normal `git pull origin` / `git push origin` — no changes.
- `git_checkpoint` works as today.

### Sub-node Behavior

- On becoming sub-node, `GitCoordinator.setup_sub_node(workdir, master_session_id)` runs:
  ```bash
  # master's playground path = sessions/<master_session_id>/playground/<repo_name>
  git remote set-url origin <sessions_root>/<master_session_id>/playground/<repo_name>
  ```
  `repo_name` is derived from the origin URL (last path component, strip `.git`).
- `git pull` now pulls from master's local copy (fast, no network, no auth).
- `git push` is blocked: `git_checkpoint` returns `"[sub-node] checkpoint committed locally; push handled by master session <id>"` without executing push.

### Session Cleanup

When a session stops (graceful shutdown in `session.py`'s `run_daemon_loop` finally block), call `GitCoordinator.release_master(repo_path, session_id)` for all repos it owns.

Sub-nodes whose master disappears will re-elect on next `git_checkpoint` call (master dead → take over).

### New File: `nutshell/runtime/git_coordinator.py`

```python
class GitCoordinator:
    REGISTRY_PATH = "_sessions/git_masters.json"
    LOCK_PATH = "_sessions/git_masters.lock"

    def register_master(self, repo_path: str, session_id: str) -> str:
        """Returns 'master' or 'sub'."""

    def get_master(self, repo_path: str) -> str | None:
        """Returns session_id of current master, or None."""

    def release_master(self, repo_path: str, session_id: str) -> None:
        """Remove registry entry if session_id matches."""

    def setup_sub_node(self, workdir: str, master_session_id: str) -> None:
        """Set git remote URL to master's local playground path."""
```

### Changes to `git_checkpoint.py`

- After resolving `workdir` to an absolute repo path, call `GitCoordinator.register_master()`.
- Store `role` in local variable.
- If `role == "sub"`: skip `git push`, append sub-node note to return value.
- If `role == "master"`: proceed as today.

---

## Files Changed

| File | Change |
|------|--------|
| `ui/cli/chat.py` | Add TTY detection, write `caller` to user_input event |
| `nutshell/tool_engine/providers/session_msg.py` | Write `caller: "agent"` to user_input event |
| `nutshell/runtime/ipc.py` | `poll_inputs()` passes through `caller` field |
| `nutshell/runtime/session.py` | Read `caller` from event, thread `caller_type` through `chat()` → `agent.run()` |
| `nutshell/core/agent.py` | Accept `caller_type` in `run()`, inject agent-mode block in `_build_system_parts()` |
| `nutshell/runtime/git_coordinator.py` | **New file** — GitCoordinator class |
| `nutshell/tool_engine/providers/git_checkpoint.py` | Call GitCoordinator, handle master/sub roles |

---

## Testing

- Unit tests for `GitCoordinator`: register, sub-node, dead master takeover, release
- Unit tests for caller detection: TTY mock → human, non-TTY → agent
- Unit tests for agent-mode prompt injection: verify block appears iff `caller_type == "agent"`
- Integration: two sessions on same repo → verify only master pushes

---

## Out of Scope

- Git conflict resolution between master and sub-nodes (agent's responsibility)
- Sub-node → master promotion via explicit API call
- Web UI display of master/sub status
