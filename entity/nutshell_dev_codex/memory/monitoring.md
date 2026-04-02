# Monitoring And Startup Checks

Claude has a local monitoring toolkit under `.claude/`.

## Useful Commands

Full startup check:

```bash
bash .claude/startup_check.sh
```

File delta scan only:

```bash
python .claude/check_new_files.py
```

Targeted verification baseline:

```bash
python -m pytest tests/ -v --tb=short
```

## Interpretation

- this is project instrumentation, not a built-in Codex hook
- use it when beginning broad repo work, debugging drift, or reviewing recent changes
- skip or narrow it when the task is tiny and the full check would waste time

## Persistent Reminder

If I notice unexpected repo changes or unclear state, start here before making assumptions.
