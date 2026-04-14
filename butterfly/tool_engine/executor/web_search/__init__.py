from butterfly.core.tool import Tool


def create_web_search_tool(provider: str = "brave") -> Tool:
    """Return a web_search Tool backed by the specified provider."""
    if provider == "tavily":
        from butterfly.tool_engine.executor.web_search.tavily_web_search import create_web_search_tool as _make
    else:
        from butterfly.tool_engine.executor.web_search.brave_web_search import create_web_search_tool as _make
    return _make()


__all__ = ["create_web_search_tool"]
