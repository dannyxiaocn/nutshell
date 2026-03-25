"""Automatic model selection based on task complexity.

Provides a lightweight, heuristic-based evaluator that inspects the
content of tasks.md and recommends an appropriate model tier (haiku /
sonnet / opus) without making any LLM calls.

Usage in session.py tick():
    complexity = evaluate_task_complexity(tasks_content)
    model      = suggest_model(complexity, provider)
    if model:
        agent.model = model   # temporary override
"""

from __future__ import annotations

import re

# ── Keyword sets ───────────────────────────────────────────────────

_COMPLEX_KEYWORDS: set[str] = {
    "implement", "architect", "design", "refactor", "migrate",
    "debug", "analyse", "analyze", "investigate", "build",
}

_SIMPLE_KEYWORDS: set[str] = {
    "check", "list", "status", "ping", "remind",
    "note", "log", "summary",
}

# Pre-compiled word-boundary patterns for efficient matching.
_COMPLEX_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _COMPLEX_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
_SIMPLE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SIMPLE_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ── Model maps per provider ───────────────────────────────────────

_MODEL_MAP: dict[str, dict[str, str]] = {
    "anthropic": {
        "simple":  "claude-haiku-4-5-20251001",
        "medium":  "claude-sonnet-4-6",
        "complex": "claude-opus-4-6",
    },
    "openai": {
        "simple":  "gpt-4o-mini",
        "medium":  "gpt-4o",
        "complex": "o3",
    },
}


# ── Public API ─────────────────────────────────────────────────────

def evaluate_task_complexity(tasks_content: str) -> str:
    """Classify task content as 'simple', 'medium', or 'complex'.

    Pure text heuristics — no LLM call.

    Rules:
      * complex : word count > 300  OR  contains a complex keyword
      * simple  : word count < 80   AND  (contains a simple keyword OR no complex keyword)
      * medium  : everything else
    """
    text = (tasks_content or "").strip()
    if not text:
        return "simple"

    word_count = len(text.split())
    has_complex = bool(_COMPLEX_RE.search(text))
    has_simple = bool(_SIMPLE_RE.search(text))

    # Long text → always complex
    if word_count > 300:
        return "complex"

    # Complex keyword present → complex (regardless of length)
    if has_complex:
        return "complex"

    # Short text with simple keyword (or no complex keyword) → simple
    if word_count < 80:
        return "simple"

    # Everything else → medium
    return "medium"


def suggest_model(complexity: str, provider: str | None) -> str | None:
    """Return the recommended model string for *complexity* on *provider*.

    Returns ``None`` for unknown providers (no override).
    """
    provider_key = (provider or "anthropic").lower()
    mapping = _MODEL_MAP.get(provider_key)
    if mapping is None:
        return None
    return mapping.get(complexity)
