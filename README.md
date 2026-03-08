# Nutshell `v0.1.1`

A minimal Python agent runtime. Agents run as persistent server-managed instances, accessible via a terminal UI or web browser — no Python required to create or run an agent.

---

## How It Works

Nutshell is built around a **server + frontend** model:

```
nutshell-server          ← always-on backend (manages all instances)
nutshell-tui             ← terminal UI frontend
nutshell-web             ← web UI frontend (http://localhost:8080)
```

The server and UIs communicate only through files on disk — no network sockets between them. This means you can open multiple UIs against the same server, attach and detach freely, and the server keeps running when you close a UI.

---

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-...

# 3. Start the server (keep this running)
nutshell-server

# 4. Open a UI (in another terminal, or browser)
nutshell-tui --create my-agent   # terminal UI, creates new instance
nutshell-web                      # web UI at http://localhost:8080
```

---

## Instance Lifecycle

An **instance** is a running agent session. Every instance has its own directory under `instances/`:

```
instances/my-agent/
├── manifest.json    ← created by UI; tells server which entity to load
├── kanban.md        ← task board (read/written by the agent)
├── context.json     ← conversation log: "turn" events with full Anthropic-format messages
├── inbox.jsonl      ← UI → server (append-only)
├── outbox.jsonl     ← server → UI (append-only, tailed by UI)
├── daemon.pid       ← server PID while instance is running
└── files/           ← attached files
```

### States

```
[created]  →  [active]  ←→  [sleeping]
                  ↑               ↓
              user msg        agent done
                  ↑               ↓
              /start          /stop (heartbeat paused)
```

| State | What's happening |
|-------|-----------------|
| **active** | Agent is currently running (`agent.run()` in progress) |
| **sleeping** | Agent is idle, loop polls every 0.5s for inbox + heartbeat |
| **stopped** | `status: stopped` in manifest; heartbeat paused; still accepts user messages |

### What wakes an instance

1. **User message** — UI writes to `inbox.jsonl`; instance picks it up within 0.5s. A stopped instance is automatically un-stopped when a user message arrives.
2. **Heartbeat** — every `heartbeat_interval` seconds (default: 10s), the server checks if `kanban.md` is non-empty. If so, it invokes the agent to continue work.

### Heartbeat timing

The heartbeat interval is counted **from when the previous tick completes**, not from when it starts. So if an agent takes 30s to process tasks and the interval is 10s, the next check happens 10s after it finishes — never back-to-back.

### Stop / Start

```
/stop   → sets manifest status=stopped; heartbeat pauses; user messages still work
/start  → sets manifest status=active; heartbeat resumes
```

Available in both TUI (`/stop`, `/start` commands) and Web UI (⏸/▶ buttons).
A user message always wakes a stopped instance regardless of status.

**Instance indicator** (Web UI):
- 🟢 Green — daemon running, not stopped, kanban has pending tasks
- ⚫ Grey — stopped, kanban empty, or daemon not running

### Server startup recovery

On startup, the server scans all `instances/` subdirectories. Any instance with a `manifest.json` (and `status != stopped`) is resumed automatically:

- **Conversation history** is restored from `context.json` — the agent remembers the full prior conversation including tool calls.
- **Heartbeat** resumes immediately if `kanban.md` has pending tasks.
- Instances with an empty kanban start silently (no log noise); instances with pending work log `Resumed: <id> (N messages, kanban pending)`.
- Stopped instances (`status: stopped`) are skipped until the user clicks ▶ Start.

---

## Creating an Agent

Agents are defined entirely in files — no Python needed. Each agent lives in an **entity directory**:

```
entity/
└── my-agent/
    ├── agent.yaml          ← manifest: model, tools, skills, prompt
    ├── prompts/
    │   └── system.md       ← system prompt (plain markdown)
    ├── skills/
    │   └── coding.md       ← skill definitions (YAML frontmatter + body)
    └── tools/
        └── search.json     ← tool schema (JSON Schema)
```

### `agent.yaml`

```yaml
name: my-agent
description: A focused coding assistant.
model: claude-sonnet-4-6          # or claude-haiku-4-5-20251001, etc.
release_policy: persistent        # persistent | auto | manual
max_iterations: 20

prompts:
  system: prompts/system.md

skills:
  - skills/coding.md

tools:
  - tools/search.json
```

**`release_policy`** controls conversation history:
- `persistent` — history kept across all activations (default, recommended)
- `auto` — history cleared after each `agent.run()` call
- `manual` — cleared only when explicitly closed

### `prompts/system.md`

Plain markdown. This is the agent's identity and rules. Every agent that uses the kanban board should include kanban instructions:

```markdown
You are a focused coding assistant.

## Kanban Board

You have a persistent kanban board for tracking work across sessions.
Use read_kanban to check outstanding tasks.
Use write_kanban to update the board when you finish each activation:
- Remove completed tasks.
- Leave unfinished tasks with notes on next steps.
- Call write_kanban("") when all work is done.
An empty kanban means no outstanding work remains.
```

### `skills/*.md`

Skills inject additional context into the system prompt. They use YAML frontmatter:

```markdown
---
name: coding
description: Expert coding practices
---

# Coding Standards

Always write type-annotated Python.
Prefer composition over inheritance.
Write tests for non-trivial logic.
```

### `tools/*.json`

Tool schemas follow JSON Schema format. The `name` must match a registered implementation (see [Extending with Python](#extending-with-python)):

```json
{
  "name": "search_web",
  "description": "Search the web and return top results.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Search query" }
    },
    "required": ["query"]
  }
}
```

### Using your entity

When creating an instance from the UI, specify your entity path:

```bash
# TUI
nutshell-tui --create my-agent --entity entity/my-agent

# Web UI
# Click "+ New", enter the entity path in the dialog
```

The server reads `manifest.json` written by the UI, loads your entity, and starts the agent.

---

## Terminal UI (`nutshell-tui`)

```bash
nutshell-tui                          # create new instance (timestamp ID)
nutshell-tui --create my-project      # create named instance
nutshell-tui --attach my-project      # attach to existing instance
nutshell-tui --entity entity/my-agent # use a specific entity
nutshell-tui --instances-dir ~/work/instances
```

**Layout:**

```
┌──────────────────────────────────┬──────────────────────┐
│  Chat History                    │  Kanban              │
│                                  │  ─────────────────   │
│  agent❯ I've started the tasks.  │  - Write report      │
│  you  ❯ Add one more task.       │  - Review PR         │
│  agent❯ Added to kanban.         │                      │
│                                  │  Instances           │
│                                  │  ─────────────────   │
│                                  │  ● my-project  ◀    │
│                                  │  ○ old-project       │
├──────────────────────────────────┴──────────────────────┤
│  > Type a message...                                     │
├──────────────────────────────────────────────────────────┤
│  server: running (pid 12345)  │  instance: my-project   │
└──────────────────────────────────────────────────────────┘
```

**Commands:**

| Command | Action |
|---------|--------|
| `/kanban` | Show kanban content inline |
| `/status` | Show server status and PID |
| `/stop` | Pause heartbeat for this instance |
| `/start` | Resume heartbeat |
| `/exit` | Exit TUI (server keeps running) |
| `Ctrl+N` | Create new instance |
| `q` | Quit |

---

## Web UI (`nutshell-web`)

```bash
nutshell-web                          # http://localhost:8080
nutshell-web --port 9000
nutshell-web --instances-dir ~/work/instances
```

**Features:**
- Left panel: instance list with live/stopped status indicators
- Center: real-time chat via Server-Sent Events (SSE)
- Right panel: kanban board with inline editor
- ⏸ Stop / ▶ Start buttons per instance

**API** (for custom integrations):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/instances` | List all instances (with alive/stopped/kanban status) |
| `POST` | `/api/instances` | Create instance |
| `GET` | `/api/instances/{id}/history` | Full outbox dump + current byte offset (for attach) |
| `GET` | `/api/instances/{id}/events?since=N` | SSE stream from byte offset (new events only) |
| `POST` | `/api/instances/{id}/messages` | Send user message |
| `GET` | `/api/instances/{id}/kanban` | Read kanban |
| `PUT` | `/api/instances/{id}/kanban` | Write kanban |
| `POST` | `/api/instances/{id}/stop` | Pause heartbeat |
| `POST` | `/api/instances/{id}/start` | Resume heartbeat |

---

## Project Structure

```
nutshell/
├── nutshell/
│   ├── abstract/          # ABC interfaces
│   │   ├── agent.py       # BaseAgent
│   │   ├── tool.py        # BaseTool
│   │   ├── skill.py       # BaseSkill
│   │   └── loader.py      # BaseLoader
│   ├── core/              # Runtime
│   │   ├── agent.py       # Agent — LLM loop
│   │   ├── instance.py    # Instance — persistent session + heartbeat
│   │   ├── ipc.py         # FileIPC — inbox/outbox file communication
│   │   ├── tool.py        # Tool + @tool decorator
│   │   ├── skill.py       # Skill
│   │   └── types.py       # Message, ToolCall, AgentResult
│   ├── loaders/           # Entity file loaders
│   │   ├── agent.py       # AgentLoader: entity/ → Agent
│   │   ├── prompt.py      # PromptLoader: .md → str
│   │   ├── tool.py        # ToolLoader: .json → Tool
│   │   └── skill.py       # SkillLoader: .md → Skill
│   ├── llm/               # LLM backends
│   │   ├── anthropic.py   # AnthropicProvider (default)
│   │   └── openai.py      # OpenAIProvider
│   ├── infra/             # Server infrastructure
│   │   ├── server.py      # nutshell-server entry point
│   │   └── watcher.py     # InstanceWatcher — scans instances/ directory
│   └── ui/                # Frontend UIs
│       ├── tui.py         # nutshell-tui (Textual)
│       └── web.py         # nutshell-web (FastAPI + SSE)
│
├── entity/                # Agent definitions (plain files, edit these)
│   └── agent_core/        # Default general-purpose agent
│       ├── agent.yaml
│       ├── prompts/system.md
│       ├── skills/reasoning.md
│       └── tools/echo.json
│
├── instances/             # Runtime state (auto-created)
│   └── <id>/
│       ├── manifest.json
│       ├── kanban.md
│       ├── context.json
│       ├── inbox.jsonl
│       ├── outbox.jsonl
│       └── files/
│
└── tests/
    ├── test_agent.py
    └── test_tools.py
```

---

## Extending with Python

If you want to implement tool logic in Python (vs. just defining the schema in JSON), register implementations with `ToolLoader`:

```python
from nutshell import AgentLoader
from nutshell.llm.anthropic import AnthropicProvider
from pathlib import Path

def search_web(query: str) -> str:
    # your implementation
    return f"Results for: {query}"

agent = AgentLoader(impl_registry={"search_web": search_web}).load(
    Path("entity/my-agent")
)
agent._provider = AnthropicProvider()
```

Or use the `@tool` decorator directly:

```python
from nutshell import Agent, tool
from nutshell.llm.anthropic import AnthropicProvider

@tool(description="Search the web")
async def search(query: str) -> str:
    ...

agent = Agent(
    system_prompt="You are a research assistant.",
    tools=[search],
    provider=AnthropicProvider(),
)
```

---

## Multi-Agent Patterns

### Agent-as-Tool

```python
writer = Agent(system_prompt="You are a writer.", release_policy="auto")

orchestrator = Agent(
    system_prompt="You coordinate agents.",
    tools=[writer.as_tool("write", "Write a paragraph on a topic.")],
)

result = await orchestrator.run("Write about black holes.")
```

### Sequential pipeline

```python
research = await researcher.run("Key facts about black holes")
summary  = await summarizer.run(research.content)
```

---

## Tests

```bash
pytest tests/    # uses MockProvider, no API key needed
```

---

## Changelog

### v0.1.1
- **History resume** — agent restores full conversation history (including tool calls) from `context.json` on server restart; no more "who are you?" on reconnect
- **Lossless context storage** — `context.json` now stores `"turn"` events with complete Anthropic-format messages (tool_use IDs + tool_result content preserved)
- **Inbox replay prevention** — `inbox_offset` initialized to current file size; old messages are not replayed when the server restarts
- **Heartbeat ghost output fix** — if the user stops an instance while a heartbeat is in-flight, the heartbeat result is silently discarded from the UI
- **Stop/Start indicator** — instance dot is green only when daemon is running, not stopped, and kanban has work; turns grey immediately on stop
- **Crashed instance restart** — instances that crashed can be restarted via ▶ Start without restarting the server
- **Server startup log** — discovered instances printed as one line: `Discovered: A, B, C [total N]`
- **Heartbeat UI styling** — heartbeat-triggered agent responses show `⏱ agent` label with distinct color

### v0.1.0
- Initial release: server + TUI + web UI, persistent instances, heartbeat, kanban
