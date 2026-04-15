# Web UI — Design

The web frontend serves a monitoring UI and HTTP API over the same file-backed session model used by the CLI. No second state model — everything comes from on-disk session files.

## v2.0.9 — UX polish

### Config editor
- Two views + read-only table:
  - **Form** view — structured inputs. Provider is a dropdown populated from `GET /api/models`; model becomes a dropdown keyed on the selected provider (with a `Custom…` escape hatch so power users can still type free-form model IDs). Complex fields (`tool_providers`, `prompts`, `tools`, `skills`, `duty`) remain JSON textareas to avoid building a dedicated widget per field.
  - **Raw YAML** view — edits `sessions/<id>/core/config.yaml` byte-for-byte via `GET/PUT /api/sessions/{id}/config/yaml`. Comments are dropped by PyYAML on save (noted in the editor hint).
- Backend sources model list from `butterfly/service/models_service.py` (hand-curated to match the 4 providers plus `openai-responses`). Not live-queried from provider APIs — the CLI surface is the source of truth.

### 5-second input merge window (web only)
State machine lives in `ui/web/frontend/src/components/chat.ts`:

```
 IDLE ──Enter──▶ PENDING(5s timer)
 PENDING ──new msg──▶ PENDING (reset 5s, append buffer)
 PENDING ──timer, agent idle──▶ flush → IDLE
 PENDING ──timer, agent running──▶ BUFFERED_WHILE_STREAMING
 PENDING ──"Send now"──▶ flush → IDLE
 BUFFERED_WHILE_STREAMING ──model_status=idle──▶ flush → IDLE
 BUFFERED_WHILE_STREAMING ──new msg──▶ buffer append (no timer)
 ANY ──"Interrupt & send"──▶ POST /interrupt + flush → IDLE
```

Task-layer messages (duty fires, scheduled cards) bypass this entirely — they arrive through the task runtime, not the user-input path. CLI is untouched.

Auto-interrupt hint: when the pending buffer starts with `stop|wait|no|cancel|nope|hold on`, the "Interrupt & send" button pulses. We never auto-interrupt; the user presses the button.

### HUD trim (v2.0.9)
Before: `📁 cwd · 💬 ctx 42% (85k/200k) · ⎇ 3f +21 -7 · ⚡ in:1.2k out:0.4k cache:0.1k`

After: `• model-name · ctx 42% · [▶ bash] · 1.2k↓ 0.4k↑`
- Status dot pulses green while the agent is running.
- Running-tool pill is hidden unless a tool is mid-call.
- Full cwd + full token breakdown are in `title=` tooltips.

### Tool status redesign
`msg-tool` now renders a uniform `▶ name | arg preview | ts` summary row + click-to-expand `<details>` block for full args. On `tool_done`, the row flips in place to `✓ name (duration)` (border accent switches yellow→green). No more separate `tool finished` msg-status line — keeps the log quiet, which the user explicitly asked for.

