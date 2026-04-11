# Nutshell — Todo

## Active

### Codebase Pruning (Module 8)
- [ ] `runtime/` session content → `session_engine/`: align with engine naming convention; ~30 import updates
- [ ] `loader.py` → `session_engine/`: `AgentConfig.from_path()` does file IO, belongs in session engine

### Skill Engine Deep Implementation (Module 9)
- [ ] skill frontmatter: extend to Claude Code compatible subset (allowed_tools, arguments, when_to_use, context, model)
- [ ] skill tool: access rights and context modification (tool allowlist, thinking/model override)
- [ ] skill arguments: upgrade from $ARGUMENTS to named params, defaults, escaping, error hints
- [ ] skill resources: standardized discovery of agents/, prompts/, references/ in skill dirs
- [ ] skill prompt persistence: handle multi-turn, history compact, sub-agent/fork scenarios
- [ ] skill sources: session / entity / user three-level with priority and dedup
- [ ] conditional skill activation: path-pattern or workspace-context based
- [ ] skill observability: load/use events to runtime stats
- [ ] skill engine e2e tests: provider interaction simulation

### CLI-as-Authority Follow-ups (from todo.md)
- [ ] `ui/cli/chat.py:173,206`: FileIPC direct write in cmd_chat
- [ ] `ui/web/app.py:222-223`: SSE generator direct BridgeSession use
- [ ] `ui/web/weixin.py:252-270,377-378`: direct FileIPC/write_session_status
- [ ] Parse/validate helpers from web app.py → tasks_service/config_service
- [ ] Meta-session guard from route layer → messages_service
- [ ] Duplicate params.json reads in GET /api/sessions/{id}
- [ ] Hoist function-body imports in service/*
- [ ] Missing CLI commands for 1:1 parity: info, delete, interrupt, message send, config get/set, tasks add/rm, hud
- [ ] Layering linter: tests/test_ui_layering.py
- [ ] Move frontend validation from Python to TypeScript

### Entity Inheritance Bug
- [ ] `init_session()` reads agent.yaml directly for model/provider — does not walk extends chain
- [ ] `populate_meta_from_entity()` reads params directly — does not resolve inheritance
- [ ] `own/link/append` fields defined but mostly unused outside memory/playground sync

## Backlog

- [ ] CLI-started sessions: auto background server for heartbeat, auto-stop when no pending
- [ ] Agent room mode: enter agent room instead of online chat
- [ ] Agent-agent communication protocol
- [ ] Sub-agent spawning (call sub-agent / spawn_session)
- [ ] Sub-agent ACP to OpenClaw
- [ ] Auto cache system
- [ ] Porters system completion

## Completed (Recent)

See `track.md` for full history with commit IDs.

- [x] Module 1: CLI cleanup (95c593f)
- [x] Module 2: Multi-agent + CAP (b36eb75)
- [x] Module 3: Meta-session (9472524, 6a1c5c4, d773ed7, 5d895fc)
- [x] Module 4: Entity inheritance (b4fbc50, 6bf957d)
- [x] Module 5: Thinking config (4978494, bd5d01d, 91762f5)
- [x] Module 6: Sandbox (4a48ad3, ec90b69)
- [x] Module 7: Tool stats (cb43c19, 3130b36, 369fede)
- [x] Module 8 partial: release_policy cleanup (71db1b4), hook integration (29f4996), session_type (task cards)
