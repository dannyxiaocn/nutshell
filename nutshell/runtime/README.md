# `nutshell/runtime`

This is the orchestration layer. It watches session state on disk, starts daemons, and exposes file-based communication primitives to the UI.

## What This Part Is

- `server.py`: `nutshell server` entrypoint.
- `watcher.py`: discovers `_sessions/<id>/manifest.json` and starts `Session.run_daemon_loop()`.
- `ipc.py`: file-based IPC over `context.jsonl` and `events.jsonl`.
- `bridge.py`: frontend-friendly wrapper over `FileIPC`.
- `env.py`: best-effort `.env` loader.
- `cap.py`: file-backed coordination primitives.
- `git_coordinator.py`: master/sub registration for shared git repos.

## How To Use It

Start the daemon:

```bash
nutshell server
```

Or use the client bridge:

```python
from pathlib import Path
from nutshell.runtime.bridge import BridgeSession

bridge = BridgeSession(Path("_sessions/demo"))
msg_id = bridge.send_message("hello")
```

## How It Contributes To The Whole System

- Without this layer, sessions exist only as files.
- It is responsible for turning session manifests into running agents.
- It is also the contract surface used by both CLI and Web UIs, which keeps transport simple and shared.

## Important Behavior

- `context.jsonl` stores conversation records only.
- `events.jsonl` stores runtime and UI events only.
- `watcher.py` skips sessions whose PID is already alive, so it does not race an already-running daemon.
- Stopped sessions can auto-expire back to active after several hours, depending on watcher/session logic.
- `ipc.py` `last_running_event_offset()`: returns the byte offset of the last `model_status:running` event so a re-attaching client can replay an in-progress turn. Returns `events_size()` if a subsequent `model_status:idle` is found — this prevents duplicate tool events when the session finished between history fetch and SSE open.
- Thinking blocks are emitted with per-block IDs (`thinking:{ts}:{idx}`) so multiple thinking blocks from one turn survive dedup in `BridgeSession.iter_events()`.

