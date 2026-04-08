---
name: nutshell
description: "Full development context for the nutshell project. Use this skill for any task involving nutshell: writing code, adding features, fixing bugs, running tests, bumping versions, updating docs, or understanding architecture. Load whenever working on this repo."
---

# Nutshell — Developer Skill

Complete workbench for developing nutshell.

Current version: **v1.3.4** | Tests: `pytest tests/ -q` (184 passing)

---

## Role

**You are nutshell_dev.** Claude Code dispatches tasks to you; you execute them.
- Claude Code selects tasks from `track.md`, sends you instructions, reviews your output
- You implement, test, commit, push — then report the commit ID back
- If you find bugs or missing features mid-task, fix them and add new `[ ]` items to `track.md`

## Workspace

**Always work in your playground, never modify the origin repo directly.**

```bash
# Session workdir is sessions/<id>/  — do this first:
ls playground/nutshell 2>/dev/null || git clone /Users/xiaobocheng/agent_core/nutshell playground/nutshell
cd playground/nutshell
git pull origin main
```

After completing work: `git push origin main`

---

## SOPs

### 1. After Any Code Change
```bash
# Run from playground/nutshell/
pytest tests/ -q          # must pass before anything else
```
Then:
1. Update `README.md` — relevant section + new Changelog entry
2. Bump version in **both** `pyproject.toml` AND `README.md` heading
3. Commit using the repo's current required format
4. `git push origin main`
5. Report commit ID back to Claude Code

**Versioning:** Patch (Z): bug fix · Minor (Y): new feature · Major (X): breaking

### 2. track.md Workflow

`track.md` is the project task board. Keep it up to date:
- Mark completed items `[x]` with the commit ID as `<!-- COMMIT_ID vX.Y.Z -->`
- Add new `[ ]` sub-items when you discover tasks can be further broken down
- Add new `[ ]` todos when you hit missing features or related improvements

```bash
cat track.md              # read current tasks
# edit track.md to mark done or add todos
git add track.md && git commit -m "track: ..."
```

### 3. Adding a Built-in Tool

1. Add a real implementation that the current runtime can resolve
2. Register it in `nutshell/tool_engine/registry.py` if it is a built-in tool
3. Add `entity/agent/tools/<name>.json` only after the implementation exists
4. Add it to `entity/agent/agent.yaml` only if sessions should expose it by default
5. Write or update tests
6. Run full SOP

### 4. Adding a New LLM Provider

1. `nutshell/llm_engine/providers/<name>.py` extending `Provider`
2. Register in `nutshell/llm_engine/registry.py`
3. `complete()` returns `(str, list[ToolCall], TokenUsage)` — 3-tuple
4. `complete()` accepts `on_text_chunk=None`, `cache_system_prefix=""`, `cache_last_human_turn=False`

---

## Package Layout

```
nutshell/
├── core/                  — ABCs + Agent, Tool, Skill, Provider, types
│   ├── agent.py           — Agent: run(), _history, _build_system_parts(), memory + memory_layers
│   ├── tool.py, skill.py, provider.py, types.py
│   └── loader.py          — AgentLoader (inheritance chain resolution)
├── llm_engine/
│   ├── providers/
│   │   ├── anthropic.py   — AnthropicProvider
│   │   ├── codex.py       — CodexProvider
│   │   ├── kimi.py        — KimiForCodingProvider
│   │   └── openai_api.py  — OpenAIProvider
│   ├── registry.py        — resolve_provider(name), provider_name(provider)
│   └── loader.py
├── tool_engine/
│   ├── executor/
│   │   ├── terminal/      — bash / shell executors
│   │   └── web_search/    — brave / tavily providers
│   ├── registry.py        — _BUILTIN_FACTORIES + get_builtin(name)
│   ├── loader.py          — ToolLoader: .json + built-in registry + .sh shell tools
│   ├── reload.py          — create_reload_tool(): hot-reload core/ capabilities
│   └── sandbox.py
├── skill_engine/
│   ├── loader.py          — SkillLoader: SKILL.md + flat .md
│   └── renderer.py        — build_skills_block()
├── session_engine/
│   ├── session.py         — Session: chat(), tick(), run_daemon_loop()
│   ├── session_init.py    — init_session(): copies entity → core/ (skills, tools, memory)
│   ├── session_status.py  — status.json r/w, pid_alive
│   ├── session_params.py  — params.json: DEFAULT_PARAMS, read/write/ensure_session_params
│   ├── entity_config.py   — AgentConfig: agent.yaml parsing + inheritance
│   ├── entity_state.py    — meta session management, entity sync/alignment
│   └── agent_loader.py    — AgentLoader: entity → Agent construction
└── runtime/
    ├── server.py          — nutshell-server entry point
    ├── watcher.py         — SessionWatcher: polls _sessions/, starts session tasks
    ├── ipc.py             — FileIPC: context.jsonl + events.jsonl; display converters
    └── bridge.py          — BridgeSession: client-side session handle for frontends

ui/                        (NOT inside nutshell/ package)
├── cli/
│   ├── main.py            — nutshell: unified CLI entry point
│   └── chat.py            — nutshell-chat legacy entry point
└── web/                   — FastAPI + SSE monitoring UI
```

---

## CLI (v1.3.4)

```bash
# Session management (no server required)
nutshell sessions                     # list all sessions
nutshell sessions --json              # JSON output
nutshell new [ID] [--entity NAME]     # create session
nutshell stop SESSION_ID              # pause heartbeat
nutshell start SESSION_ID             # resume heartbeat
nutshell tasks [SESSION_ID]           # show session's tasks.md
nutshell log [SESSION_ID] [-n N]      # show last N conversation turns

# Messaging
nutshell chat "message"               # new session + send
nutshell chat --session ID "message"  # continue session
nutshell chat --session ID --no-wait "message"  # fire-and-forget

# Entity management
nutshell entity new -n NAME           # scaffold new entity
nutshell review                       # review agent entity-update requests
```

---

## Entity Inheritance

```
entity/agent/              — base runtime entity
  ↑ entity/nutshell_dev/      — adds: nutshell skill, memory.md pre-seeded
    ↑ entity/nutshell_dev_codex/ — codex-tuned development variant
```

**Built-in tools** (always available):
`bash`, `web_search`, `reload_capabilities`

---

## Session Disk Layout

```
sessions/<id>/core/
  system.md        ← system prompt
  memory.md        ← persistent memory (seeded from entity on first creation)
  memory/          ← layered memory: *.md → "## Memory: {stem}" blocks
  tasks.md         ← task board (non-empty triggers heartbeat)
  params.json      ← runtime config (SOURCE OF TRUTH)
  tools/           ← .json + .sh agent-created tools
  skills/          ← <name>/SKILL.md session skills

_sessions/<id>/
  context.jsonl    ← user_input + turn events
  status.json      ← DYNAMIC: model_state, status, pid
```

---

## Key API Notes

- **`status.py` / `ipc.py`** take `system_dir` (`_sessions/<id>/`)
- **`params.py`** takes `session_dir` (`sessions/<id>/`)
- **Prompt caching**: static (system.md + session.md) cached; dynamic (memory + skills) not cached
- **`session_factory.init_session()`** — copies entity memory.md + memory/*.md → core/ on first creation
- **Working directory**: always `playground/nutshell/` — never modify origin repo path directly

---

## Running Tests

```bash
pytest tests/ -q                     # all (184 tests)
pytest tests/test_<name>.py -v       # specific module
pytest tests/ -q -k "keyword"        # filter
```

---

## Known Technical Debt

| File | Issue | Priority |
|------|-------|----------|
| `tool_engine/providers/web_search/brave.py` + `tavily.py` | `_SCHEMA` dict identical | LOW |
| `runtime/watcher.py` | Polls every second; no inotify | LOW |
