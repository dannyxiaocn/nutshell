"""Unified tool registry.

    get_builtin(name) → Callable | None
    resolve_tool_impl(tool_name, provider_name) → Callable | None
    list_providers(tool_name) → list[str]
    registered_tools() → list[str]
"""
from __future__ import annotations

import importlib
from typing import Callable


def _make_bash() -> Callable:
    from nutshell.tool_engine.executor.terminal.bash_terminal import create_bash_tool
    return create_bash_tool()._func


def _make_web_search() -> Callable:
    from nutshell.tool_engine.executor.web_search.brave_web_search import _brave_search
    return _brave_search


_BUILTIN_FACTORIES: dict[str, Callable[[], Callable]] = {
    "bash":       _make_bash,
    "web_search": _make_web_search,
}


def get_builtin(name: str) -> Callable | None:
    """Return the implementation callable for a built-in tool, or None."""
    factory = _BUILTIN_FACTORIES.get(name)
    return factory() if factory is not None else None


# ── Provider swap ─────────────────────────────────────────────────────────────

_PROVIDER_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    "web_search": {
        "brave":  ("nutshell.tool_engine.executor.web_search.brave_web_search",  "_brave_search"),
        "tavily": ("nutshell.tool_engine.executor.web_search.tavily_web_search", "_tavily_search"),
    },
}


def resolve_tool_impl(tool_name: str, provider_name: str) -> Callable | None:
    """Return the async impl callable for (tool_name, provider_name), or None if unknown."""
    providers = _PROVIDER_REGISTRY.get(tool_name, {})
    entry = providers.get(provider_name)
    if not entry:
        return None
    module_path, func_name = entry
    try:
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    except (ImportError, AttributeError):
        return None


def list_providers(tool_name: str) -> list[str]:
    return list(_PROVIDER_REGISTRY.get(tool_name, {}).keys())


def registered_tools() -> list[str]:
    return list(_PROVIDER_REGISTRY.keys())
