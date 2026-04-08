# nutshell_dev_codex

## Purpose

The Codex-oriented variant of `nutshell_dev`. It keeps the same project role but ships Codex-specific defaults and memory.

## How To Use It

```bash
nutshell new --entity nutshell_dev_codex
nutshell chat --entity nutshell_dev_codex "review this subsystem"
```

## How It Contributes To The Whole System

It is the repo's provider-specific developer template for the Codex workflow, so project memory and behavior stay coherent even when the runtime backend changes.

## Notes

- Use this variant when the session should default to the Codex provider flow.
- It stays aligned with `nutshell_dev` but can diverge in provider-specific memory and defaults.

## Directory Map

- [memory/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/nutshell_dev_codex/memory/README.md)
