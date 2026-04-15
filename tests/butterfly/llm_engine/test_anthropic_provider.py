from types import SimpleNamespace

import pytest

from butterfly.core.types import Message
from butterfly.llm_engine.providers.anthropic import AnthropicProvider


class _FakeStream:
    def __init__(self, events, final_message):
        self._events = events
        self._final_message = final_message

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        async def _gen():
            for event in self._events:
                yield event

        return _gen()

    async def get_final_message(self):
        return self._final_message


@pytest.mark.asyncio
async def test_complete_streams_thinking_via_thinking_hooks_not_text_chunks():
    """Thinking deltas MUST NOT leak into the main on_text_chunk stream.

    v2.0.9 redesign: provider emits on_thinking_start()/on_thinking_end(body)
    around the thinking block. on_text_chunk only receives assistant text.
    """
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.max_tokens = 123

    final_message = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="reasoning..."),
            SimpleNamespace(type="text", text="final answer"),
        ]
    )
    events = [
        SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="thinking")),
        SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="thinking_delta", thinking="reasoning..."),
        ),
        SimpleNamespace(type="content_block_stop"),
        SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="text")),
        SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="text_delta", text="final answer"),
        ),
        SimpleNamespace(type="content_block_stop"),
    ]
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(
            stream=lambda **kwargs: _FakeStream(events, final_message),
        )
    )

    chunks: list[str] = []
    thinking_starts: list[None] = []
    thinking_bodies: list[str] = []
    content, tool_calls, usage = await provider.complete(
        messages=[Message(role="user", content="hi")],
        tools=[],
        system_prompt="system",
        model="claude-test",
        on_text_chunk=chunks.append,
        on_thinking_start=lambda: thinking_starts.append(None),
        on_thinking_end=thinking_bodies.append,
    )

    # Assistant-text channel stays clean
    assert chunks == ["final answer"]
    # Thinking lifecycle landed on the dedicated hooks
    assert len(thinking_starts) == 1
    assert thinking_bodies == ["reasoning..."]
    assert content == "final answer"
    assert tool_calls == []


@pytest.mark.asyncio
async def test_complete_emits_thinking_lifecycle_when_stream_has_no_thinking_delta():
    """Non-stream fallback path: final message has a thinking block but the
    stream never yielded one. We still synthesize on_thinking_start +
    on_thinking_end from the final message, and the text chunk is clean.
    """
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.max_tokens = 123

    final_message = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="reasoning..."),
            SimpleNamespace(type="text", text="final answer"),
        ]
    )
    events = [
        SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="text")),
        SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="text_delta", text="final answer"),
        ),
        SimpleNamespace(type="content_block_stop"),
    ]
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(
            stream=lambda **kwargs: _FakeStream(events, final_message),
        )
    )

    chunks: list[str] = []
    thinking_starts: list[None] = []
    thinking_bodies: list[str] = []
    content, tool_calls, usage = await provider.complete(
        messages=[Message(role="user", content="hi")],
        tools=[],
        system_prompt="system",
        model="claude-test",
        on_text_chunk=chunks.append,
        on_thinking_start=lambda: thinking_starts.append(None),
        on_thinking_end=thinking_bodies.append,
    )

    assert chunks == ["final answer"]
    assert len(thinking_starts) == 1
    assert thinking_bodies == ["reasoning..."]
    assert content == "final answer"
    assert tool_calls == []


@pytest.mark.asyncio
async def test_complete_collects_tool_calls_from_final_message():
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.max_tokens = 123

    final_message = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text=""),
            SimpleNamespace(type="tool_use", id="tool-1", name="search", input={"q": "abc"}),
        ]
    )
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(
            create=_async_return(final_message),
        )
    )

    content, tool_calls, usage = await provider.complete(
        messages=[Message(role="user", content="hi")],
        tools=[],
        system_prompt="system",
        model="claude-test",
    )

    assert content == ""
    assert len(tool_calls) == 1
    assert tool_calls[0].id == "tool-1"
    assert tool_calls[0].name == "search"
    assert tool_calls[0].input == {"q": "abc"}


def _async_return(value):
    async def _inner(**kwargs):
        return value

    return _inner
