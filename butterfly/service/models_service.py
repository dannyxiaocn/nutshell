"""Model catalog service — provider → model list for the web UI.

Derived from the 4 providers the CLI supports (see butterfly/llm_engine/registry.py).
The list is deliberately hand-curated rather than queried live: the point of
the web config UI is to match exactly what the CLI exposes, including default
models picked by providers when ``model`` is left blank.
"""
from __future__ import annotations

from typing import Any


# Curated list of providers and their most common models.
# default_model mirrors each provider's DEFAULT_MODEL / documented default.
# Model strings here match the CLI and entity/<name>/config.yaml literals.
_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "provider": "anthropic",
        "label": "Anthropic Claude",
        "env": ["ANTHROPIC_API_KEY"],
        "supports_thinking": True,
        "thinking_style": "budget",  # int budget_tokens
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


_THINKING_EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh"]


def get_models_catalog() -> dict[str, Any]:
    """Return the full catalog consumed by the web UI config editor.

    Shape:
        {
          "providers": [
            {"provider": "...", "label": "...", "env": [...],
             "supports_thinking": bool, "thinking_style": str|None,
             "default_model": "...", "models": [...]},
            ...
          ],
          "thinking_efforts": [...],
        }
    """
    return {
        "providers": [dict(p) for p in _MODEL_CATALOG],
        "thinking_efforts": list(_THINKING_EFFORTS),
    }
