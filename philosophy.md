# Nutshell Philosophy

1. **core/ is the cleanest agent loop** — Provider, Tool, Skill, Hook, and the iteration over them. Zero IO, zero scheduling, zero lifecycle.
2. **session_engine/ calls the agent loop** — it owns when to activate (heartbeat, user input), where to persist (context.jsonl), and session lifecycle (start/stop/archive).
3. **Engines fill the loop's slots** — llm_engine → Provider, tool_engine → Tools, skill_engine → Skills.
4. **entity/ is assets, not execution** — read-only config (prompts, tools, skills) seeded into sessions at creation.
5. **Filesystem is the API** — agents read/write their session dir; UI and server communicate via context.jsonl + events.jsonl. No sockets.
6. **Delete before you add** — if a function has no caller outside tests, delete it and its tests.
