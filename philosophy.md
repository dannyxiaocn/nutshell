# Nutshell Philosophy

1. core/ is the cleanest agent loop — Provider, Tool, Skill, Hook, and the iteration over them. Zero IO, zero scheduling, zero lifecycle.
3. Engines fill the loop's slots — llm_engine → Provider, tool_engine → Tools, skill_engine → Skills, session_engine → Session calling the agent loop.
4. runtime/ is the central coordinator.
5. entity/ is assets — read-only config (prompts, tools, skills) seeded into sessions at creation.
6. Filesystem as agent's backend — agents read/write their session dir; UI and server communicate via context.jsonl + events.jsonl. No sockets.
7. nutshell puts cli as the primary user interface.
8. porters system is the central system for evaluating and maintaining the system. They are the only one that can update the changes.
