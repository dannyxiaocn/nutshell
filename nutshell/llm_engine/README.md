# llm_engine — LLM Provider Configuration Guide

## Overview

`llm_engine` wraps multiple LLM backends behind a single `Provider` interface.
The provider key is set in `agent.yaml` (entity default) or overridden per-session
in `sessions/<id>/core/params.json`.

```
nutshell/llm_engine/
├── registry.py          # provider key → class mapping; resolve_provider(name) → Provider
└── providers/
    ├── anthropic.py     # "anthropic"          — Claude models
    ├── openai_api.py      # "openai"           — GPT / any OpenAI-compat endpoint
    ├── kimi.py          # "kimi-coding-plan"   — Kimi For Coding (Moonshot AI)
    └── codex.py         # "codex-oauth"        — OpenAI Codex via ChatGPT Plus OAuth

nutshell/runtime/agent_loader.py   # AgentLoader — entity dir → Agent (extends chain,
                                   # prompts, tools, skills); calls resolve_provider()
                                   # from llm_engine as the runtime→llm_engine boundary
```

---

## Selecting a Provider

**In `agent.yaml`** (entity-level default):
```yaml
provider: anthropic        # or openai / kimi-coding-plan / codex-oauth
model:    claude-sonnet-4-6
```

**Per-session override** — edit `sessions/<session_id>/core/params.json`:
```json
{
  "provider": "openai",
  "model": "gpt-4o"
}
```
Changes take effect on the next agent activation (no restart needed).

---

## Provider 1 — Anthropic (`anthropic`)

**Class:** `AnthropicProvider`  
**Features:** streaming, prompt caching (`cache_control`), extended thinking

### Credentials

| What | Where |
|------|-------|
| API key | `ANTHROPIC_API_KEY` environment variable |
| Custom base URL (optional) | `ANTHROPIC_BASE_URL` environment variable |

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# optional: point to a proxy / local gateway
export ANTHROPIC_BASE_URL="https://your-proxy.example.com"
```

### Recommended Models

| Model ID | Use case |
|----------|----------|
| `claude-opus-4-6` | Highest capability |
| `claude-sonnet-4-6` | Default — balanced speed + quality |
| `claude-haiku-4-5-20251001` | Fastest / cheapest |

### Extended Thinking

Enable in `params.json`:
```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "thinking": true,
  "thinking_budget": 8000
}
```

---

## Provider 2 — OpenAI (`openai`)

**Class:** `OpenAIProvider`  
**Features:** streaming, tool-calling, OpenAI-compatible endpoints (e.g. local vLLM, LM Studio, Azure)

### Credentials

| What | Where |
|------|-------|
| API key | `OPENAI_API_KEY` environment variable |
| Custom base URL (optional) | `OPENAI_BASE_URL` environment variable |

```bash
export OPENAI_API_KEY="sk-..."
# optional: custom endpoint (Azure, vLLM, LM Studio, etc.)
export OPENAI_BASE_URL="https://your-azure-endpoint.openai.azure.com/openai/deployments/gpt-4o"
```

### Recommended Models

```yaml
model: gpt-4o          # best general
model: gpt-4o-mini     # fast / cheap
model: o3              # reasoning
model: gpt-5.4         # latest (if available)
```

### Compatible Endpoints

Any server that implements the OpenAI Chat Completions API works by setting
`OPENAI_BASE_URL`. Examples:
- **Azure OpenAI** — set base URL + key from your Azure resource
- **vLLM / LM Studio** — `http://localhost:8000/v1`
- **OpenRouter** — `https://openrouter.ai/api/v1` with their API key

---

## Provider 3 — Kimi For Coding (`kimi-coding-plan`)

**Class:** `KimiForCodingProvider`  
**Features:** streaming, tool-calling; uses Anthropic messages API format  
**Limitations:** no prompt caching, no extended thinking

### Credentials

| What | Where |
|------|-------|
| API key | `KIMI_FOR_CODING_API_KEY` environment variable |
| Fallback key name | `KIMI_API_KEY` (checked if primary is absent) |

```bash
export KIMI_FOR_CODING_API_KEY="your-kimi-key"
```

The base URL is hardcoded to `https://api.kimi.com/coding/` — no configuration needed.

### Recommended Models

```yaml
model: kimi-k2-5   # Kimi K2 (default coding model)
```

---

## Provider 4 — OpenAI Codex via ChatGPT OAuth (`codex-oauth`)

**Class:** `CodexProvider`  
**Endpoint:** `https://chatgpt.com/backend-api/codex/responses`  
**Features:** streaming, tool-calling, encrypted reasoning traces  
**Requirement:** **ChatGPT Plus or Pro subscription**

This provider uses the same OAuth tokens that the official `codex` CLI writes to
`~/.codex/auth.json`. Tokens are refreshed automatically — no manual renewal needed
as long as the refresh token is valid.

### Full Authentication Setup

#### Step 1 — Install the Codex CLI

```bash
npm install -g @openai/codex
# or
npx @openai/codex --version   # run without global install
```

#### Step 2 — Login

```bash
codex login
```

This opens a browser, completes the OAuth PKCE flow with `auth.openai.com`, and
writes credentials to `~/.codex/auth.json`:

```jsonc
{
  "tokens": {
    "access_token":  "eyJ...",   // short-lived JWT (~1 hour)
    "refresh_token": "...",       // long-lived, used for auto-renewal
    "id_token":      "...",
    "account_id":    "..."
  }
}
```

Nutshell reads this file directly — **no environment variable needed**.

#### Step 3 — Verify

```bash
cat ~/.codex/auth.json | python3 -c "
import json, sys, base64, time
auth = json.load(sys.stdin)
tok = auth['tokens']['access_token']
payload = json.loads(base64.urlsafe_b64decode(tok.split('.')[1] + '=='))
exp = payload.get('exp', 0)
print('Expires:', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp)))
print('Valid:  ', time.time() < exp)
"
```

#### Step 4 — Configure Entity

```yaml
# agent.yaml
provider: codex-oauth
model: codex-mini-latest   # or: codex-nano, o4-mini, o3
```

Or per-session:
```json
{
  "provider": "codex-oauth",
  "model": "codex-mini-latest"
}
```

### Token Lifecycle

| Event | What happens |
|-------|-------------|
| Token expires (< 5 min left) | Auto-refreshed using `refresh_token` before each call |
| Refresh token missing / expired | `RuntimeError` — run `codex login` again |
| `~/.codex/auth.json` absent | `RuntimeError` — run `codex login` |

Refreshed tokens are written back to `~/.codex/auth.json` automatically.

### Recommended Models

```yaml
model: codex-mini-latest   # fast, good for code tasks
model: o4-mini             # reasoning, cost-effective
model: o3                  # highest reasoning capability
```

---

## Environment Variable Summary

| Provider key | Required env var | Optional env var |
|--------------|-----------------|-----------------|
| `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| `kimi-coding-plan` | `KIMI_FOR_CODING_API_KEY` | `KIMI_API_KEY` (fallback) |
| `codex-oauth` | *(none — reads `~/.codex/auth.json`)* | — |

### Recommended: `.env` or shell profile

```bash
# ~/.zshrc or ~/.bash_profile
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export KIMI_FOR_CODING_API_KEY="..."
# codex-oauth: run `codex login` once, no env var needed
```

---

## Fallback Provider

Entities can declare a fallback for error recovery:

```yaml
# agent.yaml
provider: codex-oauth
model: codex-mini-latest
fallback_provider: anthropic
fallback_model: claude-haiku-4-5-20251001
```

If the primary provider raises an exception, the agent retries with the fallback.

---

## Adding a New Provider

1. Create `nutshell/llm_engine/providers/<name>_provider.py` implementing `Provider` ABC:
   ```python
   from nutshell.core.provider import Provider

   class MyProvider(Provider):
       async def complete(self, messages, tools, system_prompt, model, **kwargs):
           ...  # return (text: str, tool_calls: list[ToolCall], usage: TokenUsage)
   ```
2. Register in `nutshell/llm_engine/registry.py`:
   ```python
   "my-key": ("nutshell.llm_engine.providers.my_provider", "MyProvider"),
   ```
3. Use via `provider: my-key` in `agent.yaml` or `params.json`.
