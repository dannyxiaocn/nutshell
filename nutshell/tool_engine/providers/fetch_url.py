"""fetch_url — built-in tool to fetch a URL and return its text content."""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

from nutshell.tool_engine.sandbox import WebSandbox

_DEFAULT_MAX_CHARS = 8000
_TIMEOUT = 15
_SKIP_TAGS = {"script", "style", "head", "nav", "footer", "aside"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
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
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


def _html_to_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
        return extractor.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()


async def fetch_url(*, url: str, max_chars: int = _DEFAULT_MAX_CHARS, sandbox: WebSandbox | None = None) -> str:
    if sandbox is not None:
        violation = await sandbox.check('fetch_url', {'url': url})
        if violation is not None:
            return violation

    req = urllib.request.Request(url, headers={"User-Agent": "Nutshell/1.0 (agent research tool)"})
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

    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
    try:
        text = raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace")

    if "html" in content_type.lower():
        text = _html_to_text(text)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
    if sandbox is not None:
        text = await sandbox.filter_result('fetch_url', text)
    return text
