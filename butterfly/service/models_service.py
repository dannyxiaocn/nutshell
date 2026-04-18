"""Model catalog service — provider → model list for the web UI.

Derived from the 4 providers the CLI supports (see butterfly/llm_engine/registry.py).
The list is deliberately hand-curated rather than queried live: the point of
the web config UI is to match exactly what the CLI exposes, including default
models picked by providers when ``model`` is left blank.

Per-model parameters that matter at runtime (context window, reasoning-token
support) live in ``butterfly/llm_engine/models.yaml``; this service re-exports
``max_context_tokens`` onto every model entry so the frontend can size the
context-% bar without hardcoding a duplicate catalog.
"""
from __future__ import annotations

from typing import Any

from butterfly.llm_engine.model_catalog import get_max_context_tokens, get_model_spec


# Curated list of providers and their most common models.
# default_model mirrors each provider's DEFAULT_MODEL / documented default.
# Model strings here match the CLI and agenthub/<name>/config.yaml literals.
# Effort vocabularies differ by provider. `xhigh` is codex-only — sending it
# to openai-responses 400s at agent-start. We expose each provider's supported
# list so the web UI can render a filtered dropdown (PR #24 review item 7/13).
_EFFORTS_CODEX = ["none", "minimal", "low", "medium", "high", "xhigh"]
_EFFORTS_RESPONSES = ["none", "minimal", "low", "medium", "high"]
_EFFORTS_BUDGET_OR_NONE: list[str] = []  # providers with budget-based or no thinking

_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "provider": "anthropic",
        "label": "Anthropic Claude",
        "env": ["ANTHROPIC_API_KEY"],
        "supports_thinking": True,
        "thinking_style": "budget",  # int budget_tokens
        "supported_efforts": _EFFORTS_BUDGET_OR_NONE,
        "default_model": "claude-sonnet-4-6",
        "models": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
    },
    {
        "provider": "openai",
        "label": "OpenAI (Chat Completions)",
        "env": ["OPENAI_API_KEY"],
        "supports_thinking": False,
        "thinking_style": None,
        "supported_efforts": _EFFORTS_BUDGET_OR_NONE,
        "default_model": "gpt-4o",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4.1",
            "gpt-4.1-mini",
        ],
    },
    {
        "provider": "openai-responses",
        "label": "OpenAI (Responses API, reasoning)",
        "env": ["OPENAI_API_KEY"],
        "supports_thinking": True,
        "thinking_style": "effort",  # none/minimal/low/medium/high
        "supported_efforts": _EFFORTS_RESPONSES,
        "default_model": "gpt-5",
        "models": [
            "gpt-5",
            "gpt-5-codex",
            "gpt-5.4",
            "o4-mini",
            "o3",
            "o3-mini",
            "o1",
            "o1-mini",
        ],
    },
    {
        "provider": "kimi-coding-plan",
        "label": "Moonshot Kimi (for coding)",
        "env": ["KIMI_FOR_CODING_API_KEY"],
        "supports_thinking": True,
        "thinking_style": "extra_body",
        "supported_efforts": _EFFORTS_BUDGET_OR_NONE,
        "default_model": "kimi-for-coding",
        "models": [
            "kimi-for-coding",
            "kimi-k2",
            "kimi-k1.5",
        ],
    },
    {
        "provider": "codex-oauth",
        "label": "Codex (ChatGPT OAuth)",
        "env": [],  # uses ~/.codex/auth.json
        "supports_thinking": True,
        "thinking_style": "effort",  # none/minimal/low/medium/high/xhigh
        "supported_efforts": _EFFORTS_CODEX,
        "default_model": "gpt-5.4",
        "models": [
            "gpt-5.4",
            "gpt-5",
            "gpt-5-codex",
            "o4-mini",
            "o3",
            "o3-mini",
        ],
    },
]


# Union of all provider-supported efforts. The web UI should key its dropdown
# off each provider's `supported_efforts` field rather than this global list.
_THINKING_EFFORTS = _EFFORTS_CODEX


def _enrich_models(entries: list[str]) -> list[dict[str, Any]]:
    """Attach per-model runtime parameters (max_context_tokens) to each entry.

    Models not yet declared in models.yaml fall back to the module-level
    default inside ``get_max_context_tokens``; they still render, they just
    size the HUD at the default window. Keeping the shape as a list of
    ``{name, max_context_tokens}`` dicts (rather than a parallel array) so
    the frontend's lookup stays O(1) and tolerant to re-ordering.
    """
    out: list[dict[str, Any]] = []
    for name in entries:
        spec = get_model_spec(name)
        out.append({
            "name": name,
            "max_context_tokens": spec.max_context_tokens if spec else get_max_context_tokens(name),
            "exposes_reasoning_tokens": bool(spec.exposes_reasoning_tokens) if spec else False,
        })
    return out


def get_models_catalog() -> dict[str, Any]:
    """Return the full catalog consumed by the web UI config editor.

    Shape:
        {
          "providers": [
            {"provider": "...", "label": "...", "env": [...],
             "supports_thinking": bool, "thinking_style": str|None,
             "default_model": "...",
             "models": [{"name": "...", "max_context_tokens": int,
                         "exposes_reasoning_tokens": bool}, ...]},
            ...
          ],
          "thinking_efforts": [...],
        }

    v2.0.19: ``models`` entries are enriched dicts (used to be bare strings).
    The web config editor reads ``.name`` for the dropdown label.
    """
    providers: list[dict[str, Any]] = []
    for p in _MODEL_CATALOG:
        entry = dict(p)
        entry["models"] = _enrich_models(list(p["models"]))
        providers.append(entry)
    return {
        "providers": providers,
        "thinking_efforts": list(_THINKING_EFFORTS),
    }
