"""Default web_fetch provider: plain HTTP GET via `httpx` + article extraction.

Extraction strategy (first available wins):
  1. trafilatura (best, optional dep)
  2. BeautifulSoup4 (good, optional dep)
  3. Naive regex strip of `<[^>]+>` tags + whitespace collapse (always works)

`httpx` is a transitive dependency of `anthropic>=0.40`, so no new hard dep is
added to `pyproject.toml`.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional


_USER_AGENT = "ButterflyAgent/2.0.5 (+https://github.com/dannyxiaocn/butterfly-agent)"
_TIMEOUT_SECONDS = 30
_DEFAULT_MAX_CHARS = 20000


# ── Extraction helpers ────────────────────────────────────────────────────────


def _extract_title_naive(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title or None


def _extract_with_trafilatura(html: str, url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        import trafilatura  # type: ignore
    except Exception:
        return None, None
    try:
        body = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
        )
    except Exception:
        body = None
    title: Optional[str] = None
    try:
        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            title = getattr(meta, "title", None)
    except Exception:
        title = None
    return title, body


def _extract_with_bs4(html: str) -> tuple[Optional[str], Optional[str]]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None, None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None, None

    title: Optional[str] = None
    if soup.title and soup.title.string:
        title = re.sub(r"\s+", " ", soup.title.string).strip() or None

    # Drop obvious non-content nodes.
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    # Prefer <article> / <main>, then <body>.
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = root.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return title, (text or None)


def _extract_naive(html: str) -> tuple[Optional[str], str]:
    title = _extract_title_naive(html)
    # Strip script/style blocks wholesale first.
    cleaned = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return title, cleaned


def _extract(html: str, url: str) -> tuple[Optional[str], str]:
    title, body = _extract_with_trafilatura(html, url)
    if body:
        return title, body
    t2, body = _extract_with_bs4(html)
    if body:
        return (title or t2), body
    t3, body = _extract_naive(html)
    return (title or t3), body


# ── Fetch ─────────────────────────────────────────────────────────────────────


class HttpxFetcher:
    """Fetch a URL via httpx and return extracted main text."""

    def __init__(self, timeout: float = _TIMEOUT_SECONDS, user_agent: str = _USER_AGENT) -> None:
        self._timeout = timeout
        self._user_agent = user_agent

    async def execute(self, url: str, max_chars: int | float = _DEFAULT_MAX_CHARS) -> str:
        try:
            import httpx  # type: ignore
        except Exception as exc:
            return f"Error: httpx is required for web_fetch but not installed: {exc}"

        try:
            max_chars_int = int(max_chars)
        except Exception:
            max_chars_int = _DEFAULT_MAX_CHARS
        if max_chars_int <= 0:
            max_chars_int = _DEFAULT_MAX_CHARS

        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
        }

        async def _do_fetch() -> "httpx.Response":
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout,
                headers=headers,
            ) as client:
                return await client.get(url)

        try:
            # Belt-and-suspenders: enforce a hard ceiling even if httpx's own
            # timeout machinery misfires (e.g. pathological DNS stalls).
            resp = await asyncio.wait_for(_do_fetch(), timeout=self._timeout + 5)
        except asyncio.TimeoutError:
            return f"Error: Timed out fetching {url}"
        except Exception as exc:
            # httpx.TimeoutException is a subclass of httpx.HTTPError; detect it first.
            exc_name = type(exc).__name__
            if "Timeout" in exc_name:
                return f"Error: Timed out fetching {url}"
            reason = str(exc) or exc_name
            return f"Error: Could not reach {url}: {reason}"

        if resp.status_code >= 400:
            return f"Error: HTTP {resp.status_code} fetching {url}"

        raw = resp.content or b""
        byte_len = len(raw)
        try:
            html = resp.text
        except Exception:
            html = raw.decode("utf-8", errors="replace")

        title, body = _extract(html, url)
        body = body or ""
        truncated = len(body) > max_chars_int
        if truncated:
            body = body[:max_chars_int]

        title_line = f"# {title}" if title else "# (no title)"
        trunc_note = (
            f"[fetched {byte_len} bytes, truncated at {max_chars_int} chars]"
            if truncated
            else f"[fetched {byte_len} bytes]"
        )
        parts = [
            title_line,
            f"<source url: {url}>",
            "",
            body.strip(),
            "",
            trunc_note,
        ]
        return "\n".join(parts)


async def _httpx_fetch(url: str, max_chars: int | float = _DEFAULT_MAX_CHARS) -> str:
    """Module-level entry point used by the registry."""
    return await HttpxFetcher().execute(url=url, max_chars=max_chars)
