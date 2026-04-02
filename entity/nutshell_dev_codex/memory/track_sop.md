# Task Tracking SOP

Use this when working on structured nutshell tasks.

## Before Implementation

1. identify the exact requested task, not a broadened interpretation
2. inspect the relevant files first
3. write a short current-task note into `work_state.md` if the task is substantial

## During Implementation

1. prefer minimal, coherent edits
2. do not assume inherited memory exists unless it is present on disk
3. verify behavior with targeted tests or other concrete checks when possible

## After Implementation

1. update `work_state.md`
2. update entity memory if the lesson is durable for future Codex sessions
3. mention verification status explicitly

## Caution

- Codex and Claude may share the same repo but not the same local hook/runtime model
- do not rely on `.claude/` automation being automatically invoked for Codex
- if those scripts are useful, run them deliberately
