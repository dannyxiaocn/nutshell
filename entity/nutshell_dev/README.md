# nutshell_dev

## Purpose

The project-development entity for this repository. It extends `agent` with nutshell-specific memory, a project skill, and a task-picking heartbeat.

## How To Use It

```bash
nutshell new --entity nutshell_dev
nutshell chat --entity nutshell_dev "implement the next track.md item"
```

## How It Contributes To The Whole System

This is the repo's built-in self-hosting developer persona. It turns the generic runtime into a project-aware maintainer.

## Notes

- Use this entity when you want repo-aware defaults and project memory.
- It keeps the generic runtime behavior from `agent` while adding local development context.
- Use `wip-<slug>` for active implementation branches and promote them to `ready-<slug>` when they are ready for porter/merge review.

## Directory Map

- [prompts/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/nutshell_dev/prompts/README.md)
- [memory/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/nutshell_dev/memory/README.md)
- [skills/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/nutshell_dev/skills/README.md)
