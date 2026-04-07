# llm_engine

LLM provider implementations. `registry.py` maps provider keys → classes.

| Key | Class | File | Auth |
|-----|-------|------|------|
| `anthropic` | `AnthropicProvider` | `anthropic.py` | `ANTHROPIC_API_KEY` |
| `openai` | `OpenAIProvider` | `openai_api.py` | `OPENAI_API_KEY`; optional `OPENAI_BASE_URL` |
| `kimi-coding-plan` | `KimiForCodingProvider` | `kimi.py` | `KIMI_FOR_CODING_API_KEY` |
| `codex-oauth` | `CodexProvider` | `codex.py` | `~/.codex/auth.json` (run `codex login`) |

Switch provider per-session via `sessions/<id>/core/params.json`:
```json
{"provider": "openai", "model": "gpt-4o"}
```

`providers/_common.py` — shared `_parse_json_args()` used by `openai_api` and `codex`.
