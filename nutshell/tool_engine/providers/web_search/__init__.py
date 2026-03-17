"""Web search provider package.

Public interface: create_web_search_tool(provider="brave").
"""
from __future__ import annotations

from nutshell.core.tool import Tool


def create_web_search_tool(provider: str = "brave") -> Tool:
    """Return a web_search Tool backed by the specified provider."""
    if provider == "tavily":
        from nutshell.tool_engine.providers.web_search.tavily import create_web_search_tool as _make
    else:
        from nutshell.tool_engine.providers.web_search.brave import create_web_search_tool as _make
    return _make()


__all__ = ["create_web_search_tool"]
