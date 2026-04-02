# Memory

- 2026-04-02: `send_to_session` now uses QJBQ as the canonical transport via `POST /api/session-message`; retain direct `_sessions/.../context.jsonl` write only as migration/test fallback when relay is unavailable.
