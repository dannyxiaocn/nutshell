"""Web fetch executor -- delegates to the configured provider (default: httpx).

Mirrors the pattern of toolhub/web_search/executor.py so additional providers
(e.g. a headless-browser fetcher, a cached-proxy fetcher) can be added later
by dropping a sibling module and registering it in
`butterfly/tool_engine/registry.py`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent


def _get_fetch_func(provider: str):
    """Dynamically load the fetch function from a sibling module."""
    # Only `httpx` is shipped today; unknown providers fall back to httpx so a
    # mis-configured `tool_providers` entry doesn't break the tool outright.
    spec = importlib.util.spec_from_file_location("httpx_fetch", _DIR / "httpx.py")
    func_name = "_httpx_fetch"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)


class WebFetchExecutor:
    """Unified web-fetch executor that delegates to the configured provider."""

    def __init__(self, provider: str = "httpx") -> None:
        self._provider = provider

    async def execute(self, **kwargs: Any) -> str:
        fetch_func = _get_fetch_func(self._provider)
        return await fetch_func(**kwargs)
