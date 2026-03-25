# track.md SOP

## Reading Tasks

1. `cat track.md` at repo root to see current task board
2. Look for `[ ]` (unchecked) items — these are pending tasks
3. **Do not self-select tasks.** Wait for Claude Code to dispatch a specific task to you.

## Completing Tasks

1. Implement the feature / fix as instructed
2. Run `pytest tests/ -q` — all tests must pass
3. Update `README.md`: add/edit the relevant section + new Changelog entry
4. Bump version in **both** `pyproject.toml` and `README.md` heading
5. Commit: `git commit -m "vX.Y.Z: short summary\n\n- bullet points"`
6. Note the commit hash

## Updating track.md

1. Mark the completed item: `[ ]` → `[x]`
2. Append commit reference: `<!-- COMMIT_ID vX.Y.Z -->`
3. If you discovered sub-tasks or missing features during work, add new `[ ]` items
4. Commit track.md separately: `git add track.md && git commit -m "track: mark <task> done"`
5. Report the feature commit ID back to Claude Code
