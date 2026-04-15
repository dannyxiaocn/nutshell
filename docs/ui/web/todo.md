# Web UI — Todo

## Active

- [ ] Migrate SSE generator to streaming service interface
- [ ] Migrate WeChat direct writes to service layer
- [ ] Move frontend validation from Python to TypeScript

## Completed

- [x] SSE reconnect with byte-offset tracking
- [x] Loop lifecycle events (loop_start, loop_end, tool_done) in SSE stream
- [x] Task card UI with CRUD endpoints
- [x] HUD endpoint
- [x] **v2.0.9** — Config editor redo: structured form + raw-YAML mode, backed by new `GET/PUT /api/sessions/{id}/config/yaml` and `GET /api/models`
- [x] **v2.0.9** — 5-s user-input merge window with "Send now" / "Interrupt & send" affordances (web-only; task and CLI paths untouched)
- [x] **v2.0.9** — HUD trimmed to: dot · model · ctx% · current-tool · tokens
- [x] **v2.0.9** — Tool status uniform `▶ name …` / `✓ name (duration)` with click-to-expand args; removed standalone `tool finished` log lines
