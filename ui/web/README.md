# `ui/web`

The Web frontend for Nutshell. It serves a monitoring UI and a small HTTP API over the same file-backed session model used by the CLI.

## What This Part Is

- `app.py`: FastAPI app, routes, SSE stream, and HUD endpoint.
- `sessions.py`: helper functions for session metadata and initialization.
- `weixin.py`: optional WeChat bridge.
- `frontend/`: Vite + TypeScript SPA. Run `npm run build` to compile; the resulting `dist/` is committed and served by `app.py` at `/`.

## How To Use It

```bash
nutshell-web
# or
nutshell-web --port 8080 --sessions-dir ./sessions
```

Key endpoints:

- `GET /api/sessions`
- `POST /api/sessions`
- `POST /api/sessions/{id}/messages`
- `GET /api/sessions/{id}/events?context_since=N&events_since=N` — SSE stream; each event payload includes `_ctx`/`_evt` byte offsets for reconnect advancement
- `GET /api/sessions/{id}/history?context_since=N` — returns all display events from `context_since` onward plus `context_offset`/`events_offset` for SSE attach; when session is actively running, `events_offset` points to the last `model_status:running` line so the client can replay the in-progress turn
- `GET /api/sessions/{id}/tasks` — returns task cards from `core/tasks/`; migrates legacy `core/tasks.md` on read
- `PUT /api/sessions/{id}/tasks` — create or update a task card; returns 409 if renaming to an existing name
- `DELETE /api/sessions/{id}/tasks/{name}` — remove one task card
- `GET /api/sessions/{id}/config`
- `PUT /api/sessions/{id}/config`
- `GET /api/sessions/{id}/hud` — returns cwd, context size, git diff stats, last token usage for the HUD bar

## Frontend Architecture

The SPA (`frontend/src/`) is a TypeScript + Vite app:

- `main.ts` — session attach with monotonic version token (prevents stale history/config from a previous attach overwriting a new one); `visibilitychange` handler fetches and renders only new events since last render
- `sse.ts` — `SSEConnection`: tracks `contextSince`/`eventsSince` and advances them from each received event's `_ctx`/`_evt` fields so reconnects resume from the latest offset, not the original attach point; `reconnectWithOffsets(sessionId, ctx, evt)` is session-guarded
- `components/chat.ts` — message batching captures session ID at enqueue time; `appendEvent` inserts events before the streaming bubble when one is active so the "generating…" indicator always stays at the bottom
- `components/sidebar.ts` — create-session form state survives re-renders via `formVisible` flag; heartbeat interval is not exposed in the create form

## How It Contributes To The Whole System

This directory gives operators a live, streaming view of session activity without introducing a second state model. Everything still comes from the on-disk session files.

- The SSE event stream includes loop lifecycle and tool completion events (`loop_start`, `loop_end`, `tool_done`) in addition to the existing agent text, tool-call, and model-status updates.
