# docs/nutshell/

Documentation for the Python runtime package. Each subdirectory corresponds to a `nutshell/` subsystem.

| Directory | Component |
|-----------|-----------|
| `core/` | Agent loop, types, provider interface |
| `llm_engine/` | LLM provider adapters and registry |
| `runtime/` | Watcher, IPC, bridge, coordination |
| `service/` | Shared service layer (CLI + Web) |
| `session_engine/` | Entity → meta → session lifecycle |
| `skill_engine/` | Skill loading and rendering |
| `tool_engine/` | Tool loading and executors |

Start with [design.md](design.md) for architecture overview, [impl.md](impl.md) for implementation details.
