# Tool Engine — Design

The tool engine turns tool definitions into executable `Tool` objects. Tools live in `toolhub/` (centralized) and are enabled per-entity via `tool.md`.

## Design Principles

### 1. ToolHub — Centralized Tool Management

Tools are self-contained directories under `toolhub/<name>/`:
- `tool.json` — API schema (what the LLM sees)
- `executor.py` — Python implementation

Each entity declares which tools it uses in `tool.md` (one name per line). The `ToolLoader` dynamically imports executors at session init time.

Built-in tools: `bash`, `web_search`, `skill`, `manage_task`, `recall_memory`.

### 2. Tool-Call Minimal Parameter Design

**Core principle**: agents should pass only business-intent parameters. All environmental context (paths, credentials, session state) is auto-injected by the runtime at session initialization — never passed by the agent per-call.

**How it works**:

`Session._load_session_capabilities()` creates a `ToolLoader` with all context pre-bound:

```python
loader = ToolLoader(
    default_workdir=str(self.session_dir),   # bash runs from session dir
    skills=skills,                           # skill tool has the skills list
    tasks_dir=self.tasks_dir,                # manage_task knows where tasks live
    memory_dir=self.core_dir / "memory",     # recall_memory knows memory location
)
```

`ToolLoader._create_executor()` then injects these into each executor's constructor. The agent-facing `tool.json` schema only exposes what the agent needs to decide:

| Tool | Agent passes | Auto-injected |
|------|-------------|---------------|
| `bash` | `command` | `workdir` (session dir) |
| `manage_task` | `action`, `name`, `description` | `tasks_dir` |
| `recall_memory` | `name` | `memory_dir` |
| `skill` | `skill` name | skills list |
| `web_search` | `query`, `count` | provider config |

**Why**: LLM tool calls are expensive tokens. Every parameter the agent must fill is a chance for hallucination, wasted context, and prompt engineering overhead. By injecting context at the runtime layer, we get:
- Smaller tool-call payloads (fewer tokens)
- No path hallucination (agent never constructs absolute paths)
- Consistent behavior (agent can't accidentally use wrong directory)
- Simpler prompts (no need to tell agents "pass tasks_dir=...")

**Design rule**: if a parameter's value is deterministic within a session, it must be auto-injected, not agent-provided.

### 3. Session-Authored Tools

Agents can create tools at runtime as `.json` + `.sh` pairs in `core/tools/`. The `.sh` script receives all kwargs as JSON on stdin and writes results to stdout. These are loaded via `ToolLoader.load_local_tools()`.

### 4. System Tools

- `reload_capabilities` is always injected by `Session` and cannot be overridden from disk
- Provider swapping (e.g., `web_search` → brave/tavily) is driven by `config.yaml` `tool_providers`

## Tool Resolution Order

1. `tool.md` listed tools → loaded from `toolhub/` (primary path)
2. Agent-created `.json` + `.sh` pairs in `core/tools/` (supplemental)
3. Legacy fallback: `core/tools/*.json` via `load_dir()` (backward compat when no `tool.md`)
