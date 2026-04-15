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

### Thinking cell redesign (v2.0.9 follow-up)

Prior behaviour leaked provider `thinking_delta` / `reasoning_*.delta` stream events directly into the same `on_text_chunk` callback that drives the main assistant-text `partial_text` channel. The web UI therefore showed partial chunks of chain-of-thought interleaved with the assistant's final answer, truncated at each 150-char flush boundary. The paths responsible for this were:

- `butterfly/llm_engine/providers/anthropic.py::_forward_stream_event` — forwarded `thinking_delta` bodies to `on_text_chunk`.
- `butterfly/llm_engine/providers/codex.py::_parse_sse_stream` — forwarded `response.reasoning_text.delta` and `response.reasoning_summary_text.delta` to `on_text_chunk`.
- `butterfly/llm_engine/providers/openai_responses.py::_stream` — same pattern as codex.

All three are fixed. Thinking text is now routed through a pair of dedicated provider-level callbacks and a pair of IPC events:

| Backend hook | IPC event | UI effect |
|---|---|---|
| `on_thinking_start()` | `thinking_start {block_id}` | Insert a `msg-thinking-running` cell reading `💭 Thinking…` (yellow accent, pulsing dots). |
| `on_thinking_end(text)` | `thinking_done {block_id, text, duration_ms}` | Replace the running cell with a `<details>` that summarises `💭 Thought for Xs`; body is the full collected thinking text (collapsed by default). |

Deltas are never emitted to the SSE stream — they stay server-side and are flushed as a single body on block close (matches the user's "don't stream thinking in real time" spec).

For providers that return only encrypted / opaque reasoning (OpenAI Responses with `include=reasoning.encrypted_content`, Codex under the same flag), `on_thinking_end` fires with `text=""`. The UI shows the "Thought for Xs" pill with a body placeholder — the cell still appears so the user knows the model did reason, it just has no rendered text to display.

The completed `turn` written to `context.jsonl` now carries a `has_streaming_thinking` flag symmetric to `has_streaming_tools`. Live SSE replay suppresses the old inline-thinking emit when that flag is set, so thinking cells don't render twice after a reconnect. History replay (`?context_since=…` on `/history`) still re-emits from turn content so pre-v2.0.9 sessions continue to show their reasoning.

### YAML PUT hardening (v2.0.9 review fix)

`service/config_service.py::update_config` now whitelist-filters the inbound params against `DEFAULT_CONFIG.keys()` before calling `write_config`. Previously a client could persist arbitrary keys via `PUT /api/sessions/{id}/config` or `.../config/yaml`, and they'd round-trip forever via `read_config`'s `{**DEFAULT_CONFIG, **raw}` merge. `session_config.write_config` also switched to an atomic tempfile + `os.replace` write so a concurrent read never sees a half-written file (the YAML PUT is now network-reachable).

### Pending-buffer session-switch fix (v2.0.9 review fix)

`chat.ts`'s `currentSession` handler now flushes the 5-s merge buffer if the user switches to a different session mid-window. Previously the pending bar lingered on the new session with the previous session's text, and "Send now" silently targeted the old session id.

