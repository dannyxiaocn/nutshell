---
name: nutshell
description: Load and understand the entire project structure and context. Use this skill when you need comprehensive knowledge about the project architecture, file organization, configuration files, existing entities, skills, tools, and their relationships. This skill provides a bird's-eye view of the codebase.
---

# Nutshell - Project Context Skill

This skill gives you complete visibility into the entire project structure. Use it whenever you need to:

1. **Understand project architecture** — Get a high-level view of how the project is organized
2. **Find specific files or configurations** — Locate entities, skills, tools, prompts
3. **Understand relationships** — See how different components connect
4. **Navigate the codebase** — Know where to look for specific functionality
5. **Check existing implementations** — Avoid duplicating work or understand patterns

## Project Structure Overview

```
.
├── entity/                    # Agent entity definitions
│   ├── agent_core/           # Base agent with core capabilities
│   │   ├── agent.yaml        # Entity manifest
│   │   ├── prompts/          # System prompts
│   │   ├── skills/           # Core skills (reasoning, skill-creator)
│   │   └── tools/            # Core tools (bash, web_search)
│   ├── kimi_core/            # Kimi-specific agent variant
│   └── nutshell_dev/         # This entity (inherits agent_core + nutshell skill)
├── sessions/                 # Session directories
│   └── {session_id}/
│       ├── params.json       # Session configuration
│       ├── tasks.md          # Task board
│       ├── prompts/memory.md # Persistent memory
│       └── _system_log/      # System internals
└── README.md                 # Project documentation
```

## Quick Reference: Key Files

### Entities
- `entity/agent_core/agent.yaml` — Base agent configuration
- `entity/kimi_core/agent.yaml` — Kimi agent variant
- `entity/nutshell_dev/agent.yaml` — This entity (with nutshell skill)

### Core Skills
- `entity/agent_core/skills/reasoning/SKILL.md` — Step-by-step reasoning
- `entity/agent_core/skills/skill-creator/SKILL.md` — Skill development toolkit
- `entity/nutshell_dev/skills/nutshell/SKILL.md` — This skill (project context)

### Core Tools
- `entity/agent_core/tools/bash.json` — Shell command execution
- `entity/agent_core/tools/web_search.json` — Web search capability

### Prompts
- `entity/agent_core/prompts/system.md` — Main system prompt
- `entity/agent_core/prompts/heartbeat.md` — Heartbeat activation prompt
- `entity/agent_core/prompts/session_context.md` — Session context template

## How to Use This Skill

When a user asks something that requires project-wide knowledge:

1. **First, consult this skill** — Read SKILL.md to understand what's available
2. **Explore as needed** — Use bash tool to list directories, read files
3. **Connect the dots** — Understand how components relate
4. **Provide informed answers** — Based on actual project state

## Common Queries

| User asks about... | You should... |
|-------------------|---------------|
| "What entities exist?" | List `entity/` directory, describe each |
| "How do skills work?" | Explain skill structure, show examples |
| "What's in the project?" | Give high-level overview from this skill |
| "How do I create a skill?" | Reference skill-creator skill |
| "Where is X configured?" | Navigate to relevant config file |
| "What tools are available?" | List tools from entity manifests |

## Exploration Commands

Use these bash commands to explore dynamically:

```bash
# List all entities
ls -la entity/

# See an entity's configuration
cat entity/{name}/agent.yaml

# List all skills across entities
find entity/ -name "SKILL.md" -type f

# Find all YAML configs
find . -name "*.yaml" -o -name "*.yml" | grep -v node_modules

# Search for specific content
grep -r "search_term" entity/ --include="*.md" --include="*.yaml"
```

## Notes

- This skill is automatically loaded for nutshell_dev entity
- The project follows a modular architecture: entities → skills → tools → prompts
- All paths in entity manifests are relative to the manifest file's directory
- Skills are self-contained with their own SKILL.md documentation
