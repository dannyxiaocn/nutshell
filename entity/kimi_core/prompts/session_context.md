---
## Session Files

Your session directory: `sessions/{session_id}/`

- `params.json` — session config: `model`, `provider`, `heartbeat_interval`. Edit via bash.
- `tasks.md` — task board. Use `read_tasks`/`write_tasks` tools (they update UI), or read via bash.
- `prompts/memory.md` — persistent memory. Auto-appended to this prompt each activation. Edit via bash.
- `skills/` — session-level skills (.md, YAML frontmatter). Loaded each activation. Write/delete via bash.
- `_system_log/` — system internals (context, events, manifest, status). Do not edit.
