# Runtime — Todo

## Completed

- [x] CAP (coordination primitives) module (b36eb75)
- [x] Git coordinator for multi-agent repos
- [x] Hook-driven runtime events: loop_start, loop_end, tool_done (29f4996)
- [x] IPC reconnect offset tracking

## Future

- [ ] Move session-related content from runtime/ to session_engine/ (naming alignment)
- [ ] WebSocket alternative to JSONL polling (optional, for low-latency use cases)
- [ ] **Filesystem-watcher for capability hot-reload** — replace the removed `reload_capabilities` tool (deleted in v2.0.5). When `sessions/<id>/core/tools.md`, `core/skills.md`, `core/tools/`, `core/skills/`, `core/config.yaml`, or `core/memory/` change, reload capabilities automatically on the next agent activation (inotify on Linux, FSEvents on macOS, polling fallback elsewhere). Must be debounced (≥250ms) and skip reloads while `_agent_lock` is held.
