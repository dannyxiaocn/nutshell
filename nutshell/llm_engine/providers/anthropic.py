from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable

from nutshell.core.provider import Provider
from nutshell.core.types import Message, ToolCall

if TYPE_CHECKING:
    from nutshell.core.tool import Tool


class AnthropicProvider(Provider):
    """LLM provider backed by Anthropic Claude."""

    def __init__(
        self,
        api_key: str | None = None,
        max_tokens: int = 8096,
        base_url: str | None = None,
    ) -> None:
        try:
            import anthropic as _anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic") from None
        self._client = _anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self.max_tokens = max_tokens

    async def complete(
        self,
        messages: list[Message],
        tools: list["Tool"],
        system_prompt: str,
        model: str,
        *,
        on_text_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        api_messages = _to_api_messages(messages)
        api_tools = [t.to_api_dict() for t in tools] if tools else []

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": api_messages,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        saw_streamed_thinking = False
        if on_text_chunk is not None:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if _forward_stream_event(event, on_text_chunk):
                        saw_streamed_thinking = True
                response = await stream.get_final_message()
        else:
            response = await self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "thinking":
                thinking_text = _extract_thinking_text(block)
                if thinking_text and on_text_chunk is not None and not saw_streamed_thinking:
                    on_text_chunk(thinking_text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return content_text, tool_calls


def _forward_stream_event(event: Any, on_text_chunk: Callable[[str], None]) -> bool:
    if getattr(event, "type", None) != "content_block_delta":
        return False

    delta = getattr(event, "delta", None)
    delta_type = getattr(delta, "type", None)
    if delta_type == "text_delta":
        text = getattr(delta, "text", None)
        if text:
            on_text_chunk(text)
        return False
    if delta_type == "thinking_delta":
        thinking = getattr(delta, "thinking", None)
        if thinking:
            on_text_chunk(thinking)
            return True
    return False


def _extract_thinking_text(block: Any) -> str:
    thinking = getattr(block, "thinking", None)
    if isinstance(thinking, str):
        return thinking
    text = getattr(block, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _to_api_messages(messages: list[Message]) -> list[dict]:
    result = []
    for msg in messages:
        if msg.role == "tool":
            result.append({"role": "user", "content": msg.content})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result
