# Memory

- 2026-04-02: `send_to_session` now uses QJBQ as the canonical transport via `POST /api/session-message`; retain direct `_sessions/.../context.jsonl` write only as migration/test fallback when relay is unavailable.
- 2026-04-02: Introduced CAP (`nutshell/runtime/cap.py`) as the supervised protocol layer for multi-agent coordination, with primitives `handshake`, `lock`, `broadcast`, `heartbeat-sync`; `git_coordinator` is the first CAP adapter.
