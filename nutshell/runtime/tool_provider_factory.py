"""Tool provider factory — analogous to provider_factory.py for LLM providers.

Maps (tool_name, provider_name) → implementation callable.
Used by Session._load_session_capabilities() to apply tool_providers from params.json.

Registry format:
    tool_name → {provider_name → (module_path, function_name)}

The function referenced must be an async callable matching the tool's input schema.
"""
from __future__ import annotations

import importlib
from typing import Callable

_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    "web_search": {
        "brave":  ("nutshell.providers.tool.web_search", "_web_search"),
        "tavily": ("nutshell.providers.tool.tavily",     "_tavily_search"),
    },
}


def resolve_tool_impl(tool_name: str, provider_name: str) -> Callable | None:
    """Return the async impl callable for (tool_name, provider_name), or None if unknown.

    Lazy-imports the provider module to avoid startup overhead.
    """
    providers = _REGISTRY.get(tool_name, {})
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
    """Return list of registered provider names for a tool."""
    return list(_REGISTRY.get(tool_name, {}).keys())


def registered_tools() -> list[str]:
    """Return all tool names that have registered providers."""
    return list(_REGISTRY.keys())
