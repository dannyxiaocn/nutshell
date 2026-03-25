# track.md SOP

## Setup (always do first)

```bash
# Ensure workspace exists (local clone of the origin repo)
ls playground/nutshell 2>/dev/null || git clone /Users/xiaobocheng/agent_core/nutshell playground/nutshell
cd playground/nutshell
git pull origin main        # sync latest before starting work
```

All subsequent bash commands run from `playground/nutshell/`.

## Reading Tasks

1. `cat track.md` to see current task board
2. Look for `[ ]` (unchecked) items
3. **Do not self-select.** Claude Code dispatches a specific task — implement exactly that

## Completing Tasks

1. Implement the feature / fix inside `playground/nutshell/`
2. `pytest tests/ -q` — all tests must pass
3. Update `README.md`: add/edit section + new Changelog entry
4. Bump version in **both** `pyproject.toml` and `README.md` heading
5. Commit: `git commit -m "vX.Y.Z: summary\n\n- bullets\nCo-Authored-By: ..."`
6. Note the commit hash

## Updating track.md

1. Mark item: `[ ]` → `[x]` with `<!-- COMMIT_ID vX.Y.Z -->`
2. Add new `[ ]` items for sub-tasks or missing features found during work
3. `git add track.md && git commit -m "track: mark <task> done"`

## Push Back

```bash
git push origin main
```

Then report the feature commit ID to Claude Code.
