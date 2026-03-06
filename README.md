# Nutshell

A minimal Python Agent library. Simple by design.

```python
from nutshell import Agent, Instance, AnthropicProvider, tool

@tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b

agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=[add],
    model="claude-haiku-4-5-20251001",
    provider=AnthropicProvider(),
)

# Every agent runs inside an Instance — persistent context with built-in heartbeat
async with Instance(agent=agent) as instance:
    result = await instance.chat("What is 17 + 25?")
    print(result.content)
```

---

## Install

```bash
pip install -e .              # installs anthropic + pyyaml
pip install openai            # optional: OpenAI support
pip install pytest pytest-asyncio  # for tests
```

---

## Architecture

Nutshell is organized into three layers:

```
Layer 1 — nutshell/          Core framework: Agent, Instance, Tool, Skill, providers, loaders
Layer 2 — nutshell/infra/    Agent scheduling infrastructure (placeholder)
Layer 3 — entity/            Agent content: prompt files, tool schemas, skill definitions
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

**The default runtime for every agent.** An Instance wraps an Agent with:

- **Persistence** — disk-backed `context.json` (IO event log) and `files/` directory
- **Kanban board** — `kanban.md` for tracking work across sessions
- **Built-in heartbeat** — periodic autonomous activation when kanban is non-empty
- **Concurrency safety** — `asyncio.Lock` ensures `chat()` and `tick()` never run concurrently

```
instances/
└── 2026-03-07_14-30-00/
    ├── kanban.md        ← free-form task tracking (read/write by agent)
    ├── context.json     ← full IO event log
    └── files/           ← associated files
```

```python
from nutshell import Instance, Agent

instance = Instance(
    agent=agent,
    heartbeat=10.0,          # seconds between autonomous ticks (default: 10)
    on_tick=lambda r: print(r.content),
    on_done=lambda: print("All done!"),
)

# Context manager: start() on enter, stop() on exit
async with instance:
    result = await instance.chat("Hello")

# Or resume a previous session
instance = Instance.resume("2026-03-07_14-30-00", agent=agent)
```

**Activation modes:**

| Method | Description |
|--------|-------------|
| `chat(message)` | User-driven conversation, logs to context.json |
| `tick()` | Single heartbeat: runs agent if kanban non-empty |
| `start()` / `stop()` | Start/stop background heartbeat task |
| `silence()` | Disable on_tick/on_done callbacks (for background-only mode) |

**Heartbeat loop logic:**

```
wait interval seconds
  → tick()
    → kanban empty?  → on_done() → exit
    → kanban non-empty? → agent.run() → on_tick(result) → wait again
```

### Kanban Board

Every Instance injects two tools into its agent automatically:

| Tool | Description |
|------|-------------|
| `read_kanban()` | Read current kanban content |
| `write_kanban(content)` | Overwrite kanban. `write_kanban("")` signals all work done |

The kanban is the **only** completion signal — an empty kanban stops the heartbeat.

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
from nutshell.providers.openai import OpenAIProvider

provider = AnthropicProvider(api_key="sk-...")   # or ANTHROPIC_API_KEY env var
provider = OpenAIProvider(api_key="sk-...")       # or OPENAI_API_KEY env var
```

---

## Interactive CLI

`chat.py` is a full-featured terminal chat that demonstrates the Instance + heartbeat system:

```bash
python chat.py                              # uses entity/chat_core, heartbeat=10s
python chat.py --entity entity/agent_core  # load a different entity
python chat.py --heartbeat 20              # override heartbeat interval
python chat.py --resume 2026-03-07_14-30-00  # resume a previous instance
python chat.py --model claude-opus-4-6     # override model
```

**Commands during chat:**

```
/clear      Clear conversation history
/system     Print current system prompt
/system <p> Change system prompt
/tools      List loaded tools
/skills     List loaded skills
/kanban     Show current kanban board
/exit       Exit
```

**Heartbeat behavior in chat:**

- During chat (user typing or agent responding): heartbeat is fully blocked
- After user exits: heartbeat starts, continues running silently until kanban is cleared
- Exit message: `Instance continues running: instances/<id>/`

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
├── nutshell/                  # Layer 1: Core framework
│   ├── abstract/              # Pure abstract base classes
│   │   ├── agent.py           # BaseAgent(ABC)
│   │   ├── tool.py            # BaseTool(ABC)
│   │   ├── skill.py           # BaseSkill(ABC)
│   │   └── loader.py          # BaseLoader(ABC, Generic[T])
│   ├── core/                  # Concrete implementations
│   │   ├── agent.py           # Agent(BaseAgent)
│   │   ├── instance.py        # Instance — persistent runtime + heartbeat
│   │   ├── tool.py            # Tool(BaseTool) + @tool decorator
│   │   ├── skill.py           # Skill(BaseSkill)
│   │   └── types.py           # Message, ToolCall, AgentResult
│   ├── loaders/               # External file loaders
│   │   ├── agent.py           # AgentLoader: entity/ → Agent
│   │   ├── prompt.py          # PromptLoader: .md → str
│   │   ├── tool.py            # ToolLoader: .json → Tool
│   │   └── skill.py          # SkillLoader: .md+frontmatter → Skill
│   ├── infra/                 # Layer 2: Scheduling (placeholder)
│   │   └── scheduler.py
│   └── providers/
│       ├── anthropic.py
│       └── openai.py
│
├── entity/                    # Layer 3: Agent content (plain files)
│   ├── agent_core/            # General-purpose base agent
│   │   ├── agent.yaml
│   │   ├── prompts/system.md  # Includes kanban board instructions
│   │   ├── tools/echo.json
│   │   └── skills/reasoning.md
│   └── chat_core/             # Chat CLI agent
│       ├── agent.yaml
│       └── prompts/system.md
│
├── instances/                 # Runtime: created automatically
│   └── <timestamp>/
│       ├── kanban.md
│       ├── context.json
│       └── files/
│
├── examples/
│   ├── 01_basic_agent.py
│   ├── 02_custom_tools.py
│   ├── 03_multi_agent.py
│   ├── 04_tmp_subagent.py
│   ├── 05_entity_agent.py
│   └── 06_heartbeat_agent.py  # Instance + kanban + heartbeat
│
├── chat.py                    # Interactive CLI (Instance-backed)
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
  └── append event to context.json
```

### Heartbeat Loop

```
start_heartbeat(interval)
  └── loop:
      ├── wait interval seconds
      ├── tick()
      │   ├── kanban empty? → return None (skip)
      │   └── agent.run(kanban_prompt) → on_tick(result)
      └── is_done()? → on_done() → exit
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
