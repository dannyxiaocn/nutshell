"""Model catalog loader — reads models.yaml and exposes per-model parameters.

The YAML file is the source of truth for per-model parameters that the rest
of the system needs at runtime (context window size, whether reasoning
tokens are exposed in usage). Callers should use ``get_model_spec`` or
``get_max_context_tokens`` instead of hardcoding these numbers — the web UI
frontend used to hardcode a ``_MODEL_MAX_TOKENS`` list that drifted from
reality, which is the bug this module closes.

Loading is lazy (first call) and cached. To reload after editing the YAML
at runtime, call ``reload_catalog()``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_MAX_CONTEXT = 200_000
_CATALOG_PATH = Path(__file__).with_name("models.yaml")


@dataclass(frozen=True)
class ModelSpec:
    model: str
    provider: str
    max_context_tokens: int
    exposes_reasoning_tokens: bool


_catalog: dict[str, ModelSpec] | None = None


def _load() -> dict[str, ModelSpec]:
    if not _CATALOG_PATH.exists():
        return {}
    raw: Any = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    models = raw.get("models") or {}
    specs: dict[str, ModelSpec] = {}
    for name, entry in models.items():
        if not isinstance(entry, dict):
            continue
        specs[name] = ModelSpec(
            model=name,
            provider=entry.get("provider") or "",
            max_context_tokens=int(entry.get("max_context_tokens") or _DEFAULT_MAX_CONTEXT),
            exposes_reasoning_tokens=bool(entry.get("exposes_reasoning_tokens", False)),
        )
    return specs


def _ensure_loaded() -> dict[str, ModelSpec]:
    global _catalog
    if _catalog is None:
        _catalog = _load()
    return _catalog


def reload_catalog() -> None:
    """Drop the cached catalog so the next access re-reads models.yaml."""
    global _catalog
    _catalog = None


def get_model_spec(model: str | None) -> ModelSpec | None:
    if not model:
        return None
    return _ensure_loaded().get(model)


def get_max_context_tokens(model: str | None, default: int = _DEFAULT_MAX_CONTEXT) -> int:
    spec = get_model_spec(model)
    return spec.max_context_tokens if spec else default


def all_specs() -> dict[str, ModelSpec]:
    return dict(_ensure_loaded())


__all__ = [
    "ModelSpec",
    "all_specs",
    "get_max_context_tokens",
    "get_model_spec",
    "reload_catalog",
]
