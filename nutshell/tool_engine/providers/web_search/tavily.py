"""Web search tool using the Tavily Search API.

Requires TAVILY_API_KEY environment variable.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from nutshell.core.tool import Tool
from nutshell.tool_engine.sandbox import WebSandbox
from nutshell.tool_engine.sandbox import WebSandbox


def _tavily_search_sync(
    query: str,
    count: int,
    country: Optional[str],
    language: Optional[str],
    freshness: Optional[str],
    date_after: Optional[str],
    date_before: Optional[str],
) -> tuple[str, str]:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return "https://api.tavily.com/search", "Error: TAVILY_API_KEY environment variable is not set."

    payload: dict = {
        "api_key": api_key,
        "query": query,
        "max_results": min(max(1, count), 10),
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }

    url = "https://api.tavily.com/search"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return url, f"Error: Tavily API returned HTTP {e.code}: {body[:500]}"
    except Exception as e:
        return url, f"Error: {e}"

    results = response.get("results") or []
    if not results:
        return url, "No results found."

    lines: list[str] = []
    for i, r in enumerate(results[:count], 1):
        title = r.get("title") or "(no title)"
        url_str = r.get("url") or ""
        content = r.get("content") or ""
        published = r.get("published_date") or ""
        lines.append(f"{i}. {title}")
        if url_str:
            lines.append(f"   {url_str}")
        lines.append(f"   {('[' + published + '] ') if published else ''}{content}")
        lines.append("")

    return "\n".join(lines).rstrip()


async def _tavily_search(
    query: str,
    count: int = 5,
    country: Optional[str] = None,
    language: Optional[str] = None,
    freshness: Optional[str] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    sandbox: WebSandbox | None = None,
) -> str:
    if sandbox is not None:
        violation = await sandbox.check("web_search", {"url": "https://api.tavily.com"})
        if violation is not None:
            return violation
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _tavily_search_sync,
        query, count, country, language, freshness, date_after, date_before,
    )
    if sandbox is not None:
        result = await sandbox.filter_result('web_search', result)
    return result
    return await sandbox.filter_result("web_search", result) if sandbox is not None else result


_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query string."},
        "count": {"type": "number", "description": "Number of results (1-10). Default: 5.", "minimum": 1, "maximum": 10},
        "country": {"type": "string", "description": "2-letter country code (e.g. 'US', 'CN', 'DE')."},
        "language": {"type": "string", "description": "ISO 639-1 language code (e.g. 'en', 'zh-hans')."},
        "freshness": {"type": "string", "description": "Time filter: 'day', 'week', 'month', or 'year'."},
        "date_after": {"type": "string", "description": "Results published after this date (YYYY-MM-DD)."},
        "date_before": {"type": "string", "description": "Results published before this date (YYYY-MM-DD)."},
    },
    "required": ["query"],
}


def create_web_search_tool() -> Tool:
    return Tool(
        name="web_search",
        description=(
            "Search the web using Tavily Search. Returns titles, URLs, and descriptions. "
            "Requires TAVILY_API_KEY environment variable."
        ),
        func=_tavily_search,
        schema=_SCHEMA,
    )
