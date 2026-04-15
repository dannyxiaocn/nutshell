# Providers — Implementation

## Files

| File | Purpose |
|------|---------|
| `_common.py` | Shared helpers for parsing JSON tool arguments |
| `anthropic.py` | Anthropic Messages API, prompt-cache support, streamed thinking |
| `openai_api.py` | OpenAI Chat Completions API (legacy + non-reasoning models) |
| `openai_responses.py` | OpenAI Responses API — reasoning models (o-series / gpt-5) |
| `kimi.py` | Kimi for Coding — Anthropic-compatible; `extra_body` thinking |
| `codex.py` | ChatGPT OAuth Codex Responses API over SSE |

## Provider Notes

- **Anthropic**: thinking mode uses beta Messages namespace (`client.beta.messages`), not `client.messages`.
- **Kimi**: same adapter shape as Anthropic but thinking via `extra_body={"thinking":{"type":"enabled"}}`, no beta namespace. Base URL overridable via `KIMI_BASE_URL`.
- **OpenAI (Chat Completions)**: model-family-aware param scrubber (`_apply_model_specific_params`) routes reasoning models (`o*`, `gpt-5*`, `gpt-oss*`) to `max_completion_tokens` + `reasoning_effort`; legacy models keep `max_tokens`.
- **OpenAI Responses**: Responses API path — flat tool schema, `instructions` field separate from `input`, `max_output_tokens`, `reasoning={"effort","summary":"auto"}`, `include=["reasoning.encrypted_content"]` when thinking. Replays reasoning items on subsequent turns (see below).
- **Codex**: Responses-API over SSE against the ChatGPT-OAuth endpoint. Default model `gpt-5.4` (ChatGPT-OAuth rejects `gpt-5-codex` even though codex-rs defaults to it). The "use my default" signal is an explicit allow-list (`_is_codex_compatible_model` — `gpt-*`, `o\d+-*`, `codex-*`, `ft:gpt-*`), so Kimi/Gemini/typos no longer slip through to a 400. Token refresh is async (httpx) so it doesn't block the event loop, uses a module-level `asyncio.Lock` to serialize concurrent refreshes, and writes `~/.codex/auth.json` with `0o600`. Sends `max_output_tokens`, `prompt_cache_key`, and `session_id` header; **no cache_read_tokens have been observed in practice on the ChatGPT-OAuth backend** as of 2026-04-15, so the caching fields are best-effort. SSE parser caps buffer growth at 1 MiB. Stream error taxonomy: codes match an explicit enum (`context_length_exceeded`, `rate_limit_exceeded`, `invalid_api_key`, …) plus narrow message phrases — no loose substring matching. Reasoning items are replayed across turns with `summary: null` coerced to `[]`.

## Cross-provider fallback sanitization

When the primary provider is reasoning-aware (Codex, OpenAI Responses) and emits a `reasoning` block captured into the assistant `Message.content`, a later fallback to a non-reasoning provider (Anthropic / Kimi / OpenAI Chat Completions) used to send that opaque block verbatim and 400. Now:

- `anthropic._sanitize_content_for_anthropic` strips any block type not on Anthropic's allow-list; a fully-filtered assistant message collapses to a single `[continued]` text block.
- `openai_api._build_messages` substitutes the same `[continued]` placeholder when a filtered assistant message has no text and no tool_calls.

This keeps the default entity config (`codex-oauth` primary, `kimi-coding-plan` fallback) reliable.

## Agent fallback scope

`Agent.run` only switches to the fallback provider on `ProviderError` (butterfly taxonomy) and `OSError` (transport / DNS / TLS). `asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit`, and plain Python errors (`TypeError`, `ValueError`, `AssertionError`, …) propagate — they indicate either a deliberate cancellation or a logic bug that the fallback can't fix. The switch is logged via the `butterfly.core.agent` logger (exception type only; we do not log `str(exc)` since provider error messages can contain request bodies or secrets).

## Reasoning continuation (Codex + OpenAI Responses)

When `thinking=True`, the provider sends `include=["reasoning.encrypted_content"]` so the server returns encrypted reasoning items on each turn. The provider captures these items during the stream and surfaces them via `consume_extra_blocks()`, which the agent loop appends to the assistant `Message.content`. On the next turn `_convert_assistant` emits each reasoning block back into the request `input` verbatim, and the server resumes its chain-of-thought without re-thinking.

Every concrete provider inherits `Provider.consume_extra_blocks()` from the ABC (default: empty list), so the agent loop calls it directly.

## Error taxonomy

`butterfly/llm_engine/errors.py` exposes a normalized taxonomy providers should raise from recognizable error conditions:

| Error | When |
|-------|------|
| `AuthError` | 401/403, expired/revoked refresh token |
| `RateLimitError` | 429 with optional `retry_after` |
| `ContextWindowExceededError` | server-reported context-length stop |
| `BadRequestError` | 400 (malformed request) |
| `ServerError` | 5xx (transient) |
| `ProviderError` | base — fallback for unclassified failures |

Codex parses `response.failed` events into this taxonomy; HTTP non-200 statuses are routed through `_raise_from_status`.

## TokenUsage

`butterfly.core.types.TokenUsage` has five fields: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`. `input_tokens` is *non-cached* input across all providers (OpenAI's `prompt_tokens` has cached subtracted out so the math `input + cache_read = total input` holds uniformly).

## thinking_effort conventions

All providers accept `thinking_effort ∈ {"none", "minimal", "low", "medium", "high", "xhigh"}`. An invalid value falls back to `"medium"` uniformly (Codex / OpenAI Responses / OpenAI Chat Completions). For the Responses API an explicit `"none"` is honored by **omitting** the `reasoning` request field entirely — sending `reasoning={"effort":"none"}` would either 400 or still bill reasoning tokens depending on the model.

## Fallback provider / model

`Agent._get_fallback_provider()` returns:

- `None` when neither `fallback_provider` nor `fallback_model` is configured.
- A freshly-resolved provider when only `fallback_provider` is set.
- The primary provider instance itself when only `fallback_model` is set — the run loop then retries with the same provider class and the new model.

The run loop blocks the retry only when both the provider class AND the model would be unchanged, so "same provider, different model" is a valid fallback path.

## Adding a New Provider

1. Create `providers/<name>.py` implementing `Provider.complete()`.
2. Raise errors from `butterfly.llm_engine.errors` for recognized failures.
3. Populate `TokenUsage.reasoning_tokens` when the backend reports it.
4. If the backend has server-side state that must round-trip (e.g. encrypted reasoning), override `consume_extra_blocks()`.
5. Register in `registry.py`.
6. Document in this file.
