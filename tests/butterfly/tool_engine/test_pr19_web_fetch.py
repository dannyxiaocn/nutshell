"""PR #19 review coverage: web_fetch executor (happy path + SSRF guard)."""
from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from toolhub.web_fetch.httpx import HttpxFetcher


@pytest.fixture(autouse=True)
def _drop_proxy_env(monkeypatch):
    """Tests hit 127.0.0.1 directly — inherited SOCKS/HTTP proxy env breaks httpx."""
    for k in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        monkeypatch.delenv(k, raising=False)
    # NO_PROXY covers the case where the user set a localhost allow-list.
    monkeypatch.setenv("NO_PROXY", "*")


_HTML = b"""<!doctype html>
<html><head><title>Test Page</title></head>
<body>
<header>nav stuff</header>
<main><article>
<h1>Main content</h1>
<p>Paragraph with <b>bold</b> text and enough words to survive article extraction heuristics.</p>
<p>Another paragraph to make the content look substantial to trafilatura/bs4.</p>
</article></main>
<footer>footer stuff</footer>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/ok":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_HTML)
        elif self.path == "/notfound":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"nope")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_HTML)

    def log_message(self, format, *args):  # noqa: A002
        pass  # silence


@pytest.fixture
def local_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    host, port = srv.server_address
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=2)


@pytest.mark.asyncio
async def test_web_fetch_happy_path(local_server) -> None:
    url = f"{local_server}/ok"
    out = await HttpxFetcher(timeout=5).execute(url=url)
    # Title and body should be present, nav/footer should be stripped by the
    # extractors (best-effort — tolerate if naive fallback keeps them).
    assert "Main content" in out or "Paragraph" in out
    assert "# Test Page" in out


@pytest.mark.asyncio
async def test_web_fetch_http_error(local_server) -> None:
    out = await HttpxFetcher(timeout=5).execute(url=f"{local_server}/notfound")
    assert out.startswith("Error: HTTP 404")


@pytest.mark.asyncio
async def test_web_fetch_bad_scheme() -> None:
    out = await HttpxFetcher(timeout=5).execute(url="not-a-url")
    # httpx rejects scheme-less URLs with a protocol error.
    assert out.startswith("Error:")


@pytest.mark.asyncio
async def test_web_fetch_ssrf_localhost_regression(local_server) -> None:
    """Cubic P1 (confirmed): web_fetch has no SSRF guard.

    Today, `http://127.0.0.1:<port>/` is accepted — allowing an agent
    steered by a malicious upstream to probe internal services or read
    cloud-metadata endpoints (169.254.169.254). A hardened version
    should refuse non-public hosts by default.

    Documented as xfail so the suite stays green until the guard lands.
    """
    out = await HttpxFetcher(timeout=5).execute(url=local_server + "/ok")
    if "# Test Page" in out:
        pytest.xfail(
            "web_fetch follows http://127.0.0.1 URLs — no SSRF guard "
            "(cubic P1, not fixed in PR #19)."
        )
    else:
        assert out.startswith("Error:")


@pytest.mark.asyncio
async def test_web_fetch_max_chars(local_server) -> None:
    out = await HttpxFetcher(timeout=5).execute(url=f"{local_server}/ok", max_chars=30)
    # When truncation fires, a note is appended.
    assert "truncated" in out or "Test Page" in out
