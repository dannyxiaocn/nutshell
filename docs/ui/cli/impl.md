# CLI — Implementation

## Files

| File | Purpose |
|------|---------|
| `main.py` | Subcommand registration and top-level orchestration |
| `chat.py` | Legacy single-shot chat helper for `butterfly chat` |
| `new_agent.py` | Entity scaffolding |
| `friends.py`, `kanban.py`, `visit.py` | Read-only session views |
| `repo_skill.py` | Repo overview skill generation |

## Common Commands

```bash
butterfly chat "message"
butterfly new --entity agent
butterfly sessions
butterfly log <id>
butterfly prompt-stats <id>
butterfly token-report <id>
butterfly meta <entity>
```

## Server Auto-Start

`butterfly chat` and `butterfly new` automatically start the server daemon if it is not already running. The `_ensure_server_running()` helper checks via `_is_server_running()` and calls `_start_daemon()` if needed, passing through any custom `sessions_dir` and `system_sessions_dir` from CLI args.

## Server Management (butterfly-server)

```bash
butterfly-server                # start (auto-daemonize)
butterfly-server start          # same as above
butterfly-server stop           # graceful shutdown
butterfly-server status         # show running/stopped + PID
butterfly-server update         # reinstall package + restart
butterfly-server --foreground   # run in foreground (no daemonize)
```

All flags work at top level and on subcommands. PID stored in `_sessions/server.pid`, logs in `_sessions/server.log`.
