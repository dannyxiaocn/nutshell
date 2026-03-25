"""Tests for fetch_url and recall_memory built-in tools."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── fetch_url ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_url_returns_text_content(tmp_path):
    from nutshell.tool_engine.providers.fetch_url import fetch_url

    html = b"<html><body><h1>Hello</h1><p>World</p></body></html>"

    mock_response = MagicMock()
    mock_response.read.return_value = html
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = await fetch_url(url="http://example.com")

    assert "Hello" in result
    assert "World" in result
    # Should strip HTML tags
    assert "<html>" not in result
    assert "<body>" not in result


@pytest.mark.asyncio
async def test_fetch_url_respects_max_chars():
    from nutshell.tool_engine.providers.fetch_url import fetch_url

    long_text = "x" * 10000
    html = f"<html><body><p>{long_text}</p></body></html>".encode()

    mock_response = MagicMock()
    mock_response.read.return_value = html
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = await fetch_url(url="http://example.com", max_chars=100)

    assert len(result) <= 150  # some headroom for truncation notice


@pytest.mark.asyncio
async def test_fetch_url_handles_network_error():
    from nutshell.tool_engine.providers.fetch_url import fetch_url
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
        result = await fetch_url(url="http://example.com")

    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_fetch_url_returns_plain_text_as_is():
    from nutshell.tool_engine.providers.fetch_url import fetch_url

    text = b"plain text content here"
    mock_response = MagicMock()
    mock_response.read.return_value = text
    mock_response.headers = {"Content-Type": "text/plain; charset=utf-8"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = await fetch_url(url="http://example.com/file.txt")

    assert "plain text content here" in result


# ── recall_memory ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recall_memory_finds_matching_content(tmp_path, monkeypatch):
    from nutshell.tool_engine.providers.recall_memory import recall_memory

    # Set up session memory files
    session_id = "test-session"
    monkeypatch.setenv("NUTSHELL_SESSION_ID", session_id)

    sessions_base = tmp_path / "sessions"
    core_dir = sessions_base / session_id / "core"
    core_dir.mkdir(parents=True)

    (core_dir / "memory.md").write_text("- Project uses PostgreSQL\n- API key: abc123\n")
    memory_dir = core_dir / "memory"
    memory_dir.mkdir()
    (memory_dir / "project.md").write_text("## Project Notes\nWe are building a data pipeline.")
    (memory_dir / "user.md").write_text("## User Preferences\nPrefers Python over Java.")

    result = await recall_memory(
        query="PostgreSQL",
        _sessions_base=sessions_base,
    )

    assert "PostgreSQL" in result


@pytest.mark.asyncio
async def test_recall_memory_returns_multiple_matches(tmp_path, monkeypatch):
    from nutshell.tool_engine.providers.recall_memory import recall_memory

    session_id = "search-session"
    monkeypatch.setenv("NUTSHELL_SESSION_ID", session_id)

    sessions_base = tmp_path / "sessions"
    core_dir = sessions_base / session_id / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "memory.md").write_text("- Python is the main language\n")
    memory_dir = core_dir / "memory"
    memory_dir.mkdir()
    (memory_dir / "project.md").write_text("We write Python scripts.")
    (memory_dir / "user.md").write_text("User prefers Python over shell.")

    result = await recall_memory(query="Python", _sessions_base=sessions_base)
    assert result.count("Python") >= 2


@pytest.mark.asyncio
async def test_recall_memory_no_session_id_returns_error(monkeypatch):
    from nutshell.tool_engine.providers.recall_memory import recall_memory
    monkeypatch.delenv("NUTSHELL_SESSION_ID", raising=False)

    result = await recall_memory(query="anything")
    assert "error" in result.lower() or "no session" in result.lower()


@pytest.mark.asyncio
async def test_recall_memory_no_match_returns_empty_notice(tmp_path, monkeypatch):
    from nutshell.tool_engine.providers.recall_memory import recall_memory

    session_id = "empty-session"
    monkeypatch.setenv("NUTSHELL_SESSION_ID", session_id)

    sessions_base = tmp_path / "sessions"
    core_dir = sessions_base / session_id / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "memory.md").write_text("- Only about cats\n")

    result = await recall_memory(query="quantum physics", _sessions_base=sessions_base)
    assert "no" in result.lower() or "found" in result.lower() or len(result) < 50


# ── registry ──────────────────────────────────────────────────────────────────

def test_fetch_url_registered():
    from nutshell.tool_engine.registry import get_builtin
    assert callable(get_builtin("fetch_url"))


def test_recall_memory_registered():
    from nutshell.tool_engine.registry import get_builtin
    assert callable(get_builtin("recall_memory"))
