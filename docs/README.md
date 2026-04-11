# Nutshell Documentation

Centralized documentation for all nutshell components. This directory mirrors the source code structure — each sub-directory corresponds to a code directory and contains three standard files:

| File | Purpose |
|------|---------|
| `design.md` | Component design, architecture, and rationale. Agents read this to understand intent; write back after implementing new designs. Keep concise. |
| `impl.md` | Implementation details: files, APIs, usage examples, important behaviors. More detailed than design — this is the reference manual. |
| `todo.md` | Work log and tracking: completed work (with commit IDs), known bugs, future directions. |

## Directory Structure

```
docs/
├── nutshell/                    # The Python runtime package
│   ├── core/                    # Agent loop, types, provider interface
│   ├── llm_engine/              # LLM provider adapters
│   │   └── providers/           # Per-vendor adapter details
│   ├── runtime/                 # Watcher, IPC, bridge, coordination
│   ├── service/                 # Shared service layer (CLI + Web)
│   ├── session_engine/          # Entity → meta → session lifecycle
│   ├── skill_engine/            # Skill loading and rendering
│   └── tool_engine/             # Tool loading and executors
│       └── executor/            # Concrete tool runtimes
│           ├── skill/           # Built-in skill tool
│           ├── terminal/        # Shell execution backends
│           └── web_search/      # Search provider backends
├── entity/                      # Agent templates
│   ├── agent/                   # Base entity
│   │   ├── prompts/
│   │   ├── tools/
│   │   └── skills/
│   ├── nutshell_dev/            # Project dev entity
│   │   ├── prompts/
│   │   ├── memory/
│   │   └── skills/
│   ├── nutshell_dev_codex/      # Codex variant
│   │   └── memory/
│   └── porters/                 # Merge-verification entity
├── ui/                          # User interfaces
│   ├── cli/                     # Command-line interface
│   └── web/                     # Web UI + API
└── tests/                       # Test infrastructure
    ├── porter_system/           # Centralized pytest coverage
    ├── runtime/                 # Runtime test markers
    └── tool_engine/             # Tool engine test markers
```

## Convention

- **Agents** should read `design.md` before working on a component and update it after implementing significant changes.
- **`impl.md`** is the source of truth for "how does this work" and "how do I use it". Keep it current.
- **`todo.md`** replaces inline task tracking. Link commit IDs, note bugs, and plan future work here.
- Deeper directories inherit context from their parent's docs — no need to repeat shared information.
