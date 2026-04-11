# nutshell.service

Shared internal service layer for Nutshell CLI and Web API.

## Responsibility

This package is the only layer that should read or mutate session IPC/runtime state directly.

- `ui/web/app.py` should stay a thin HTTP adapter
- `ui/cli/main.py` should stay a thin terminal adapter
- service modules expose pure Python functions with no FastAPI or argparse dependency
- adapter migrations should preserve user-visible behavior, not just move code

## Module guide

- `sessions_service.py`: session discovery/lifecycle
- `messages_service.py`: enqueue user messages and interrupts
- `history_service.py`: history/log/token/prompt statistics plus pending-input helpers used by CLI-style log views
- `tasks_service.py`: task card CRUD
- `config_service.py`: session params/config updates
- `hud_service.py`: HUD summary data for the web UI
