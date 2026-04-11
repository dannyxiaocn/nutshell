# docs/entity/

Documentation for the entity template system. Each subdirectory corresponds to a built-in entity.

| Directory | Entity |
|-----------|--------|
| `agent/` | Base general-purpose entity |
| `nutshell_dev/` | Project development entity (extends agent) |
| `nutshell_dev_codex/` | Codex variant (extends nutshell_dev) |
| `porters/` | Merge-verification entity (extends nutshell_dev_codex) |

Start with [design.md](design.md) for the entity inheritance system, [impl.md](impl.md) for how to use and create entities.
