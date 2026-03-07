# Nutshell

A minimal Python Agent library. Simple by design.

```python
from nutshell import Agent, AnthropicProvider, tool

@tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b

agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=[add],
    model="claude-haiku-4-5-20251001",
    provider=AnthropicProvider(),
)

result = await agent.run("What is 17 + 25?")
print(result.content)
```

---

## Install

```bash
pip install -e .              # installs anthropic + pyyaml + prompt-toolkit
pip install openai            # optional: OpenAI support
pip install pytest pytest-asyncio  # for tests
```

---

## Architecture

Nutshell runs as a **server + frontend** pair. The server manages agent instances; the chat UI is one of many possible frontends.

```
nutshell/
├── abstract/    ← ABC interfaces (lowest-level dependency)
├── core/        ← Agent, Instance, IPC, Tool, Skill
├── loaders/     ← File config loaders (YAML/JSON/Markdown → Python objects)
├── llm/         ← LLM backends (Anthropic, OpenAI)
└── infra/       ← Server infrastructure (InstanceWatcher + server entry point)
```

---

## Quick Start

```bash
# Terminal 1 — start the backend server
nutshell-server
# or: python -m nutshell.infra.server

# Terminal 2 — start the chat UI
nutshell-chat                              # create new instance (random ID)
nutshell-chat --create my-project          # create named instance
nutshell-chat --attach my-project          # attach to existing instance
nutshell-chat --list                       # list all instances
```

The server watches the `instances/` directory. The chat UI writes a `manifest.json` to create a new instance; the server picks it up within 1 second.

**Commands during chat:**

```
/kanban       Show current kanban board
/instances    List all instances
/status       Show server status for this instance
/exit         Exit chat (server + instance keep running)
```

---

## Core Concepts

### Agent

The LLM reasoning unit. Configured with a system prompt, tools, skills, and a provider.

```python
agent = Agent(
    system_prompt="You are a concise assistant.",
    tools=[...],
    skills=[...],
    model="claude-haiku-4-5-20251001",
    provider=AnthropicProvider(),
    release_policy="persistent",  # "auto" | "manual" | "persistent"
    max_iterations=20,
)
```

Conversation history is maintained across `.run()` calls by default (`release_policy="persistent"`).

### Instance

**The server-side runtime for every agent.** An Instance wraps an Agent with:

- **Persistence** — disk-backed `context.json` (IO event log) and `files/` directory
- **Kanban board** — `kanban.md` for tracking autonomous work across sessions
- **Built-in heartbeat** — periodic activation when kanban is non-empty
- **IPC** — `inbox.jsonl` / `outbox.jsonl` for frontend communication
- **Concurrency safety** — `asyncio.Lock` ensures `chat()` and `tick()` never overlap

```
instances/
└── my-project/
    ├── manifest.json    ← created by chat UI; triggers server to start instance
    ├── kanban.md        ← free-form task tracking (read/write by agent)
    ├── context.json     ← full IO event log
    ├── inbox.jsonl      ← UI → server
    ├── outbox.jsonl     ← server → UI
    ├── daemon.pid       ← server PID (written while running)
    └── files/           ← associated files
```

```python
from nutshell import Instance, Agent

# Create or resume — constructor is idempotent (existing files never overwritten)
instance = Instance(agent=agent, instance_id="my-project")
ipc = FileIPC(instance.instance_dir)
await instance.run_daemon_loop(ipc)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `chat(message)` | User-driven conversation, logs to context.json + outbox |
| `tick()` | Single heartbeat: runs agent if kanban non-empty |
| `run_daemon_loop(ipc)` | Full server loop: polls inbox, fires heartbeat, writes outbox |
| `is_done()` | True when kanban is empty |

### Kanban Board

Every Instance injects two tools into its agent automatically:

| Tool | Description |
|------|-------------|
| `read_kanban()` | Read current kanban content |
| `write_kanban(content)` | Overwrite kanban. `write_kanban("")` signals all work done |

```markdown
# kanban.md (example)
- Summarize the report
- Draft follow-up email
- Update project timeline
```

### Tool

External actions executed outside the LLM loop.

```python
from nutshell import tool, Tool

@tool(description="Search the web")
async def search(query: str) -> str:
    ...

# Or construct manually
my_tool = Tool(name="search", description="Search the web", func=search_func)
```

The `@tool` decorator auto-generates JSON Schema from type annotations.

### Skill

Injects knowledge or behavior into the agent's system prompt at runtime.

```python
from nutshell import Skill

coding_skill = Skill(
    name="coding",
    description="Expert coding assistant",
    prompt_injection="Always write clean, idiomatic code.",
)

agent = Agent(skills=[coding_skill], ...)
```

### Provider

Pluggable LLM backend.

```python
from nutshell import AnthropicProvider
from nutshell.llm.openai import OpenAIProvider

provider = AnthropicProvider(api_key="sk-...")   # or ANTHROPIC_API_KEY env var
provider = OpenAIProvider(api_key="sk-...")       # or OPENAI_API_KEY env var
```

---

## External File Loaders

Load agent configuration from files instead of Python.

### AgentLoader — `entity/<name>/` → `Agent`

```python
from nutshell import AgentLoader
from pathlib import Path

agent = AgentLoader().load(Path("entity/agent_core"))
```

### Agent manifest (`agent.yaml`)

```yaml
name: agent_core
description: A general-purpose assistant.
model: claude-haiku-4-5-20251001
release_policy: persistent
max_iterations: 20

prompts:
  system: prompts/system.md

tools:
  - tools/echo.json

skills:
  - skills/reasoning.md
```

### PromptLoader / SkillLoader / ToolLoader

```python
from nutshell.loaders import PromptLoader, SkillLoader, ToolLoader

system_prompt = PromptLoader().load(Path("entity/agent_core/prompts/system.md"))
skills = SkillLoader().load_dir(Path("entity/agent_core/skills/"))
tools = ToolLoader(impl_registry={"echo": lambda text: text}).load_dir(Path("entity/agent_core/tools/"))
```

---

## Multi-Agent Patterns

### Agent-as-Tool

```python
writer = Agent(system_prompt="You are a creative writer.", release_policy="auto")

orchestrator = Agent(
    system_prompt="You coordinate other agents.",
    tools=[writer.as_tool("write_paragraph", "Write a short paragraph on a topic.")],
)

result = await orchestrator.run("Write a paragraph about the ocean.")
```

### Message Passing

```python
research = await researcher.run("Key facts about black holes")
summary  = await summarizer.run(research.content)
```

---

## AgentResult

Every `.run()` and `.chat()` returns an `AgentResult`:

```python
result.content      # str: final assistant response
result.tool_calls   # list[ToolCall]: all tool calls made this run
result.messages     # list[Message]: full conversation history
```

---

## Project Structure

```
nutshell/
├── nutshell/
│   ├── abstract/              # ABC interfaces
│   │   ├── agent.py           # BaseAgent(ABC)
│   │   ├── tool.py            # BaseTool(ABC)
│   │   ├── skill.py           # BaseSkill(ABC)
│   │   └── loader.py          # BaseLoader(ABC, Generic[T])
│   ├── core/                  # Concrete implementations
│   │   ├── agent.py           # Agent(BaseAgent)
│   │   ├── instance.py        # Instance — server-mode persistent runtime
│   │   ├── ipc.py             # FileIPC — inbox/outbox file communication
│   │   ├── tool.py            # Tool(BaseTool) + @tool decorator
│   │   ├── skill.py           # Skill(BaseSkill)
│   │   └── types.py           # Message, ToolCall, AgentResult
│   ├── loaders/               # External file loaders
│   │   ├── agent.py           # AgentLoader: entity/ → Agent
│   │   ├── prompt.py          # PromptLoader: .md → str
│   │   ├── tool.py            # ToolLoader: .json → Tool
│   │   └── skill.py           # SkillLoader: .md+frontmatter → Skill
│   ├── llm/                   # LLM backends
│   │   ├── anthropic.py       # AnthropicProvider
│   │   └── openai.py          # OpenAIProvider
│   └── infra/                 # Server infrastructure
│       ├── server.py          # Entry point: nutshell-server
│       └── watcher.py         # InstanceWatcher — polls instances/ directory
│
├── entity/                    # Agent content (plain files)
│   └── agent_core/
│       ├── agent.yaml
│       ├── prompts/system.md
│       ├── tools/echo.json
│       └── skills/reasoning.md
│
├── instances/                 # Runtime state (created automatically)
│   └── <id>/
│       ├── manifest.json
│       ├── kanban.md
│       ├── context.json
│       ├── inbox.jsonl
│       ├── outbox.jsonl
│       └── files/
│
├── examples/
│   ├── 01_basic_agent.py
│   ├── 02_custom_tools.py
│   ├── 03_multi_agent.py
│   ├── 04_tmp_subagent.py
│   ├── 05_entity_agent.py
│   ├── 06_heartbeat_agent.py  # server-mode instance + kanban
│   └── 07_daemon_instance.py
│
├── chat.py                    # Chat UI frontend (nutshell-chat)
└── tests/
    ├── test_agent.py
    └── test_tools.py
```

---

## Design Principles

### Execution Loop

```
Instance.chat(input) / Instance.tick()
  │
  ├── acquire agent_lock  (blocks concurrent chat/tick)
  │
  ├── agent.run(input)
  │   ├── 1. build system_prompt (base + skills)
  │   ├── 2. provider.complete(messages, tools, model)
  │   ├── 3. tool_calls? → execute concurrently → append → goto 2
  │   └── 4. return AgentResult
  │
  ├── release agent_lock
  └── append event to context.json + outbox.jsonl
```

### Heartbeat Loop (inside run_daemon_loop)

```
loop every 0.5s:
  ├── poll inbox.jsonl → chat() for each user message
  └── every heartbeat_interval seconds:
      └── tick()
          ├── kanban empty? → skip
          └── agent.run(kanban_prompt)
              ├── INSTANCE_FINISHED in response? → clear kanban, write outbox
              └── otherwise → write heartbeat output to outbox
```

### Tool vs Skill

| | Tool | Skill |
|-|------|-------|
| **Runs** | Outside LLM loop | Inside LLM reasoning |
| **Purpose** | Execute actions (API, I/O) | Inject domain expertise |
| **Mechanism** | LLM calls it by name | Appended to system prompt |
| **Config** | `.json` (JSON Schema) | `.md` (YAML frontmatter + body) |

---

## Tests

```bash
pytest tests/
```

Tests use a `MockProvider` — no API key required.
