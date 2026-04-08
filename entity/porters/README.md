# porters

## Purpose

The porter-maintenance entity for this repository. It extends `nutshell_dev_codex` and stays focused on reviewing merge-ready branches, fixing defects directly, aligning README files with code, and keeping all pytest coverage consolidated under `tests/porter_system/`.

## How To Use It

```bash
nutshell new --entity porters
nutshell chat --entity porters "review all ready branches"
```

## How It Contributes To The Whole System

This entity is the repository's persistent porter. It continuously checks `ready-` branches, hardens them before merge, and enforces the repo's centralized porter-system testing model.

## Notes

- `wip-` branches are considered implementation-in-progress and are not the porter's primary target.
- `ready-` branches are the porter's review surface: bugs, stale docs, and non-porter pytest sprawl should be fixed there before merge.
- The heartbeat interval is three hours.

## Directory Map

- [prompts/README.md](/Users/xiaobocheng/agent_core/nutshell/entity/porters/prompts/README.md)
