"""fetch_url — built-in tool to fetch a URL and return its text content.

Uses stdlib only (urllib). Strips HTML tags to extract readable text.
Useful for reading documentation, articles, APIs, or any web content
after a web_search identifies relevant URLs.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser


_DEFAULT_MAX_CHARS = 8000
_TIMEOUT = 15  # seconds

# Tags whose content we skip entirely (scripts, styles, etc.)
_SKIP_TAGS = {"script", "style", "head", "nav", "footer", "aside"}


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor. Skips script/style blocks."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._skip_tag = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            self._skip_tag = tag
        if tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        text = "".join(self._parts)
        # Collapse excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


def _html_to_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
        return extractor.get_text()
    except Exception:
        # Fallback: strip all tags with regex
        return re.sub(r"<[^>]+>", " ", html).strip()


async def fetch_url(*, url: str, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """Fetch a URL and return its text content.

    Args:
        url:       The URL to fetch (http or https).
        max_chars: Maximum characters to return (default: 8000).
                   Longer content is truncated with a notice.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Nutshell/1.0 (agent research tool)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return f"Error: HTTP {exc.code} fetching {url}"
    except urllib.error.URLError as exc:
        return f"Error: {exc.reason} fetching {url}"
    except Exception as exc:
        return f"Error fetching {url}: {exc}"

    # Decode
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
    try:
        text = raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace")

    # Convert HTML to plain text
    ct = content_type.lower()
    if "html" in ct:
        text = _html_to_text(text)

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"

    return text
