from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nutshell.tool_engine.providers.fetch_url import fetch_url
from nutshell.tool_engine.sandbox import WebSandbox


@pytest.mark.asyncio
async def test_web_sandbox_blocks_blocked_domain():
    sandbox = WebSandbox(blocked_domains=['example.com'])
    result = await sandbox.check('fetch_url', {'url': 'https://example.com/page'})
    assert 'blocked domain' in result


@pytest.mark.asyncio
async def test_web_sandbox_allows_normal_url():
    sandbox = WebSandbox(blocked_domains=['blocked.com'])
    result = await sandbox.check('fetch_url', {'url': 'https://example.com/page'})
    assert result is None


@pytest.mark.asyncio
async def test_web_sandbox_truncates_long_response():
    sandbox = WebSandbox(max_response_chars=10)
    result = await sandbox.filter_result('fetch_url', 'x' * 50)
    assert result.startswith('x' * 10)
    assert 'truncated' in result


@pytest.mark.asyncio
async def test_fetch_url_respects_web_sandbox_block_and_filter():
    sandbox = WebSandbox(blocked_domains=['blocked.com'], max_response_chars=20)
    blocked = await fetch_url(url='https://blocked.com', sandbox=sandbox)
    assert 'blocked domain' in blocked

    mock_response = MagicMock()
    mock_response.read.return_value = b'abcdefghijklmnopqrstuvwxyz'
    mock_response.headers = {'Content-Type': 'text/plain; charset=utf-8'}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch('urllib.request.urlopen', return_value=mock_response):
        result = await fetch_url(url='https://example.com/file.txt', max_chars=1000, sandbox=sandbox)
    assert 'truncated' in result
    assert len(result) < 100
