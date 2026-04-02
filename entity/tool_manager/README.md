# tool_manager

## Purpose
Persistent audit analyst for tool and skill usage across sessions. It aggregates audit logs, produces usage reports, and highlights efficiency patterns for maintenance work.

## Notes
- Intended to run as a persistent background entity.
- Reads session audit logs and writes aggregate reporting artifacts.
- Reports should be emitted to `_sessions/tool_stats/report.md` in markdown table form.
