# agent

The default general-purpose entity. Most sessions should start here unless they need project-specific behavior.

## Purpose

- default prompts for persistent file-backed work
- default built-in tool schemas: `bash`, `skill`, `web_search`
- the base `creator-mode` skill
- the runtime defaults for the whole entity family

## How To Use It

```bash
nutshell new --entity agent
nutshell chat --entity agent "build a small CLI"
```

## How It Contributes To The Whole System

This entity is the base template that other entities extend. It defines the common operating model that the rest of the repo builds on.

## Notes

- This is the safest default starting point for new sessions.
- Other built-in entities inherit from this template rather than replacing it.

## Directory Map

- [prompts/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/agent/prompts/README.md)
- [tools/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/agent/tools/README.md)
- [skills/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/agent/skills/README.md)
