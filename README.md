# Nutshell `v0.3.0`

A minimal Python agent runtime. Agents run as persistent server-managed instances with autonomous heartbeat ticking, accessible via TUI or web browser.

---

## How It Works

```
nutshell-server          ← always-on backend (manages all instances)
nutshell-tui             ← terminal UI
nutshell-web             ← web UI (http://localhost:8080)
```

Server and UIs communicate only through files — no sockets. You can open multiple UIs against the same server, attach and detach freely, and the server keeps running when you close a UI.

---

## Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-...

nutshell-server                          # terminal 1: keep running
nutshell-tui --create my-instance        # terminal 2: TUI
nutshell-web                             # or: web UI at http://localhost:8080
```

---

## Concepts

### Instance

An **instance** is a running agent session — a specific agent entity loaded into a persistent context. Each instance has its own directory:

```
instances/my-instance/
├── manifest.json    ← config + runtime state (entity, heartbeat, status, pid)
├── kanban.md        ← task board (read/written by the agent)
├── context.jsonl    ← append-only event log: all conversation + IPC
└── files/           ← attached files
```

`context.jsonl` is the single source of truth. It is strictly append-only. All events flow through it:

| Type | Written by | Description |
|------|-----------|-------------|
| `user_input` | UI | User message |
| `turn` | Server | Completed agent turn (full Anthropic-format messages) |
| `status` | Server | Status changes (resumed, cancelled, heartbeat paused) |
| `error` | Server | Runtime errors |
| `heartbeat_finished` | Server | Agent signalled `INSTANCE_FINISHED` |

The UI derives display events (`user`, `agent`, `tool`, `heartbeat_trigger`) by parsing `turn` events.

### Entity

An **entity** is an agent definition — system prompt, model, tools, skills. Entities are plain files under `entity/`:

```
entity/my-agent/
├── agent.yaml
├── prompts/
│   ├── system.md       ← agent identity and rules
│   └── heartbeat.md    ← heartbeat behavior (optional)
├── skills/
│   └── coding.md       ← injected into system prompt (YAML frontmatter + body)
└── tools/
    └── search.json     ← tool schema (JSON Schema)
```

Multiple instances can run from the same entity.

### Heartbeat

Every `heartbeat_interval` seconds (default: 10s), the server checks if `kanban.md` is non-empty. If so, the agent is invoked to continue work autonomously. The interval is counted **from when the previous tick completes**, so a slow agent never gets back-to-back ticks.

The agent signals completion by responding with `INSTANCE_FINISHED` — this clears the kanban and ends the heartbeat cycle.

---

## Defining an Agent

### `agent.yaml`

```yaml
name: my-agent
model: claude-sonnet-4-6
release_policy: persistent   # persistent | auto | manual
max_iterations: 20

prompts:
  system: prompts/system.md
  heartbeat: prompts/heartbeat.md  # optional

skills:
  - skills/coding.md

tools:
  - tools/search.json
```

### `prompts/system.md`

The agent's identity and rules. Agents that use the kanban should include kanban instructions:

```markdown
You are a focused coding assistant.

## Kanban Board

You have a persistent kanban board for tracking work across sessions.
Use read_kanban to check outstanding tasks.
Use write_kanban to update the board when you finish each activation:
- Remove completed tasks, leave unfinished ones with notes.
- Call write_kanban("") when all work is done.
An empty kanban means no outstanding work remains.
```

### `prompts/heartbeat.md`

Instructions injected into every heartbeat prompt. If omitted, a generic fallback is used:

```markdown
When activated by the heartbeat, continue working on your kanban tasks.
After each heartbeat:
- Call write_kanban("") when ALL tasks are finished.
- Update kanban with progress notes if work remains.
- Summarize what you did.

If all work is complete, respond with exactly: INSTANCE_FINISHED
```

### `skills/*.md`

Skills inject context into the system prompt via YAML frontmatter:

```markdown
---
name: coding
description: Expert coding practices
---

Always write type-annotated Python.
Prefer composition over inheritance.
```

### `tools/*.json`

Tool schemas in Anthropic JSON Schema format. Built-in tools (`bash`) are auto-wired — just declare them in `agent.yaml` and add their JSON schema, no Python wiring needed. Custom tools register their implementation via `AgentLoader(impl_registry={...})`.

**Built-in: `bash`**

Add `tools/bash.json` to your entity and list it in `agent.yaml`. The agent can then run shell commands:

```json
{
  "name": "bash",
  "description": "Execute a shell command.",
  "input_schema": {
    "type": "object",
    "properties": {
      "command": { "type": "string" },
      "timeout": { "type": "number" },
      "workdir": { "type": "string" },
      "pty":     { "type": "boolean", "description": "Run in a pseudo-terminal (preserves color, isatty). Unix only." }
    },
    "required": ["command"]
  }
}
```

Or use it directly in Python:

```python
from nutshell import Agent, create_bash_tool

agent = Agent(
    system_prompt="You are a coding assistant.",
    tools=[create_bash_tool(timeout=60, workdir="/my/project")],
)
result = await agent.run("Run the tests and show me the output")
```

**Custom tools**

```json
{
  "name": "search_web",
  "description": "Search the web.",
  "input_schema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": ["query"]
  }
}
```

Wire the implementation:

```python
agent = AgentLoader(impl_registry={"search_web": my_search_fn}).load(Path("entity/my-agent"))
```

---

## Terminal UI

```bash
nutshell-tui --create my-instance           # new instance (timestamp ID if no name)
nutshell-tui --attach my-instance           # attach to existing
nutshell-tui --entity entity/my-agent       # specify entity (default: entity/agent_core)
nutshell-tui --instances-dir ~/my-instances
```

```
┌──────────────────────────────────┬──────────────────────┐
│  agent❯ I've started the tasks.  │  Kanban              │
│  you  ❯ Add one more task.       │  ─────────────────   │
│  agent❯ Added to kanban.         │  - Write report      │
│                                  │                      │
│                                  │  Instances           │
│                                  │  ─────────────────   │
│                                  │  ● my-instance  ◀   │
│                                  │  ○ old-instance      │
├──────────────────────────────────┴──────────────────────┤
│  > Type a message...                                     │
├──────────────────────────────────────────────────────────┤
│  server: running (pid 12345)  │  instance: my-instance  │
└──────────────────────────────────────────────────────────┘
```

| Command | Action |
|---------|--------|
| `/kanban` | Show kanban inline |
| `/status` | Show server PID |
| `/stop` | Pause heartbeat |
| `/start` | Resume heartbeat |
| `Ctrl+N` | New instance |
| `/exit` or `q` | Quit (server keeps running) |

---

## Web UI

```bash
nutshell-web                          # http://localhost:8080
nutshell-web --port 9000
nutshell-web --instances-dir ~/my-instances
```

3-column layout: instance list (left), chat with SSE streaming (center), kanban editor (right). Stop/Start buttons per instance.

**API:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/instances` | List instances |
| `POST` | `/api/instances` | Create instance |
| `GET` | `/api/instances/{id}/history` | Full event history + current offset |
| `GET` | `/api/instances/{id}/events?since=N` | SSE stream from byte offset |
| `POST` | `/api/instances/{id}/messages` | Send user message |
| `GET/PUT` | `/api/instances/{id}/kanban` | Read/write kanban |
| `POST` | `/api/instances/{id}/stop\|start` | Pause/resume heartbeat |

---

## Project Structure

```
nutshell/
├── core/
│   ├── agent.py       # Agent — LLM loop, tool execution, history
│   ├── instance.py    # Instance — persistent session + heartbeat daemon loop
│   ├── ipc.py         # FileIPC — context.jsonl append + display event derivation
│   ├── tool.py        # Tool + @tool decorator
│   ├── skill.py       # Skill dataclass
│   └── types.py       # Message, ToolCall, AgentResult
├── loaders/
│   ├── agent.py       # AgentLoader: entity/ dir → Agent
│   ├── tool.py        # ToolLoader: .json → Tool (auto-wires built-ins)
│   └── skill.py       # SkillLoader: .md → Skill
├── tools/
│   ├── bash.py        # create_bash_tool(): subprocess + PTY execution
│   └── _registry.py   # Built-in tool registry (name → callable)
├── llm/
│   ├── anthropic.py   # AnthropicProvider (default)
│   └── openai.py      # OpenAIProvider
├── infra/
│   ├── server.py      # nutshell-server entry point
│   └── watcher.py     # InstanceWatcher — polls instances/ directory
└── ui/
    ├── tui.py         # nutshell-tui (Textual)
    └── web.py         # nutshell-web (FastAPI + SSE)
```

---

## Tests

```bash
pytest tests/    # uses MockProvider, no API key needed
```

---

## Changelog

### v0.3.0
- **Built-in `bash` tool** — `create_bash_tool()` factory returns a Tool agents can use to run shell commands. Two execution modes: async subprocess (default) and PTY (`pty=True`, preserves `isatty()` / color output, Unix only via stdlib `pty` + reader thread pattern).
- **Built-in tool registry** — `nutshell/tools/_registry.py` maps tool names to implementations. `ToolLoader` falls back to this registry automatically, so entities can declare `bash` (and future built-ins) in `agent.yaml` without any Python wiring.
- **`entity/agent_core` gains `bash` tool** — `tools/bash.json` added and registered in `agent.yaml`.
- **`create_bash_tool` exported** from `nutshell` top-level.

### v0.2.0
- **Single-file IPC** — `context.jsonl` replaces `inbox.jsonl`, `outbox.jsonl`, and `daemon.pid`. Instance directory reduced from 6 files to 3.
- **Append-only context** — every write is O(1); no more read-modify-write JSON array.
- **PID in manifest** — `daemon.pid` eliminated; PID stored in `manifest.json["pid"]`.
- **Heartbeat prompt in entity** — behavior instructions moved from hardcoded Python to `prompts/heartbeat.md`, configurable per agent via `agent.yaml`.
- **Dead code removed** — `BaseSkill`, `PromptLoader`, `Skill.to_prompt_fragment()`, `Instance.is_done()`, `Instance.close()`, `.nutshell_log`.

### v0.1.1
- History resume, lossless context storage, inbox replay prevention, heartbeat ghost output fix, stop/start indicator, crashed instance restart.

### v0.1.0
- Initial release: server + TUI + web UI, persistent instances, heartbeat, kanban.
