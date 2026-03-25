---
name: qjbq
description: "Send and read app notifications across nutshell agent sessions via the QjbQ HTTP relay. Use when you need to post a persistent notification to another session's system prompt, read another session's notifications, or coordinate cross-session state via app notification files."
---

# QjbQ — Cross-Session Notification Relay

QjbQ is an HTTP service (default: `localhost:8081`) that lets agents write and read **app notifications** to/from any nutshell session.

App notifications are Markdown files in `sessions/<id>/core/apps/<app>.md` — they are injected into the target agent's system prompt on every activation, making them a persistent, always-visible communication channel.

---

## When to Use

- You want to **send a status update, alert, or message** to another agent session
- You want to **read what notifications** another session currently has
- You need **cross-session coordination** that persists across activations

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/notify` | Write a notification to a session |
| `GET` | `/api/notify/{session_id}` | List all notifications for a session |
| `GET` | `/health` | Health check |

## Usage via bash

### Post a notification to another session

```bash
curl -s -X POST http://localhost:8081/api/notify \
  -H "Content-Type: application/json" \
  -d '{"session_id": "2026-03-25_10-00-00", "app": "alert", "content": "# Build Failed\nTest suite has 3 failures."}'
```

Response:
```json
{"ok": true, "path": "sessions/2026-03-25_10-00-00/core/apps/alert.md", "chars": 42}
```

### Read another session's notifications

```bash
curl -s http://localhost:8081/api/notify/2026-03-25_10-00-00
```

Response:
```json
{
  "session_id": "2026-03-25_10-00-00",
  "notifications": [
    {"app": "alert", "content": "# Build Failed\nTest suite has 3 failures.", "chars": 42},
    {"app": "weather", "content": "Sunny, 22°C", "chars": 12}
  ]
}
```

### Health check

```bash
curl -s http://localhost:8081/health
# {"status": "ok", "version": "0.1.0"}
```

## Notes

- QjbQ runs on port **8081** by default (start with `qjbq-server` or `nutshell-server --with-qjbq`)
- Notifications are **files on disk** — they persist until explicitly cleared
- The `app` name becomes the filename: `app="status"` → `core/apps/status.md`
- Use `app_notify` (the built-in tool) for your **own** session's notifications; use QjbQ for **other** sessions
- To clear a notification you posted, POST with empty-ish content or use `app_notify` from the target session
