from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_count_tokens_returns_tokens_text():
    from nutshell.tool_engine.providers.count_tokens import count_tokens

    result = await count_tokens("hello world", model="kimi-for-coding")
    assert "tokens" in result
    assert "model: kimi-for-coding" in result


@pytest.mark.asyncio
async def test_count_tokens_claude_uses_anthropic_counter(monkeypatch):
    from nutshell.tool_engine.providers import count_tokens as mod

    monkeypatch.setattr(mod, "_count_claude_tokens_sync", lambda text, model: 38)
    result = await mod.count_tokens("abc" * 10, model="claude-sonnet-4-6")

    assert "38 tokens" in result
    assert "estimated" not in result


@pytest.mark.asyncio
async def test_count_tokens_openai_uses_tiktoken_counter(monkeypatch):
    from nutshell.tool_engine.providers import count_tokens as mod

    monkeypatch.setattr(mod, "_count_openai_tokens_sync", lambda text, model: 12)
    result = await mod.count_tokens("hello openai", model="gpt-4o")

    assert "12 tokens" in result
    assert "estimated" not in result


@pytest.mark.asyncio
async def test_count_tokens_fallback_estimate(monkeypatch):
    from nutshell.tool_engine.providers import count_tokens as mod

    def boom(text, model):
        raise RuntimeError("no api key")

    monkeypatch.setattr(mod, "_count_claude_tokens_sync", boom)
    result = await mod.count_tokens("a" * 40, model="claude-sonnet-4-6")

    assert "10 tokens" in result
    assert "estimated" in result


def test_count_tokens_registered():
    from nutshell.tool_engine.registry import get_builtin

    assert callable(get_builtin("count_tokens"))
