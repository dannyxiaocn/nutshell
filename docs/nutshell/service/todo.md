# Service — Todo

## Active

- [ ] Migrate remaining IPC direct writes from `ui/cli/chat.py:173,206`
- [ ] Migrate SSE generator in `ui/web/app.py:222-223` to streaming service interface
- [ ] Migrate WeChat direct writes in `ui/web/weixin.py:252-270,377-378`
- [ ] Move parse/validate helpers from web app.py → tasks_service/config_service
- [ ] Move meta-session guard from route layer → messages_service
- [ ] Fix duplicate params.json reads in GET /api/sessions/{id}
- [ ] Hoist function-body imports in service/*
- [ ] Missing CLI commands for 1:1 parity: info, delete, interrupt, message send, config get/set, tasks add/rm, hud
- [ ] Layering linter: `tests/test_ui_layering.py`

## Future

- [ ] `nutshell/service/` → `nutshell/commands/`: each file = one CLI command, CLI and Web as pure dispatchers
