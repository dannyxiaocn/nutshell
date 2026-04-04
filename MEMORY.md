# Memory

- 2026-04-04: v1.3.65 — core/ pruned to cleanest agent loop. Removed: `BaseTool`, `BaseAgent`, `release_policy`, `Agent.as_tool()`, `Agent._build_system_prompt()`, `examples/`. Added: `core/hook.py` with `OnLoopStart/End/ToolCall/Done/TextChunk`. Bug fix: `session._load_session_capabilities()` now applies `fallback_model`/`fallback_provider` from params to agent. Added `philosophy.md`.
- 2026-04-02: `send_to_session` now uses QJBQ as the canonical transport via `POST /api/session-message`; retain direct `_sessions/.../context.jsonl` write only as migration/test fallback when relay is unavailable.
- 2026-04-02: Introduced CAP (`nutshell/runtime/cap.py`) as the supervised protocol layer for multi-agent coordination, with primitives `handshake`, `lock`, `broadcast`, `heartbeat-sync`; `git_coordinator` is the first CAP adapter.
- 2026-04-02: Curated the built-in entity set by adding `entity/README.md` plus per-entity `README.md` files so provider variants and internal developer entities are explicitly documented instead of remaining ambiguous.
- 2026-04-02: Meta sessions are now explicitly treated as the concrete entity instantiation layer; first bootstrap copies both memory and playground defaults from `entity/`, and child sessions inherit mutable state from `sessions/<entity>_meta/`.
