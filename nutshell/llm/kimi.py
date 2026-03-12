from __future__ import annotations
import json
import os
from typing import TYPE_CHECKING, Any, Callable

from nutshell.abstract.provider import Provider
from nutshell.core.types import Message, ToolCall

if TYPE_CHECKING:
    from nutshell.core.tool import Tool

_KIMI_BASE_URL = "https://api.kimi.com/coding/"
_KIMI_DEFAULT_MODEL = "kimi-for-coding"


class KimiProvider(Provider):
    """LLM provider backed by Kimi (Moonshot AI).

    Uses Kimi's OpenAI-compatible API, converts between the internal
    Anthropic-style message format and the OpenAI wire format.

    Args:
        api_key: Moonshot API key. Falls back to MOONSHOT_API_KEY env var.
        max_tokens: Maximum tokens in the response (default: 4096).
        base_url: API base URL (default: https://api.moonshot.ai/v1).
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_tokens: int = 4096,
        base_url: str = _KIMI_BASE_URL,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai") from None
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ.get("KIMI_API_KEY"),
            base_url=base_url,
        )
        self.max_tokens = max_tokens

    async def complete(
        self,
        messages: list["Message"],
        tools: list["Tool"],
        system_prompt: str,
        model: str,
        *,
        on_text_chunk: Callable[[str], None] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        api_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *_to_api_messages(messages),
        ]
        api_tools = [_to_openai_tool(t) for t in tools] if tools else []

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": api_messages,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        content_text = ""
        tool_calls: list[ToolCall] = []

        if on_text_chunk is not None:
            content_text, tool_calls = await self._complete_streaming(kwargs, on_text_chunk)
        else:
            response = await self._client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            content_text = message.content or ""
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        input=json.loads(tc.function.arguments),
                    ))

        return content_text, tool_calls

    async def _complete_streaming(
        self,
        kwargs: dict[str, Any],
        on_text_chunk: Callable[[str], None],
    ) -> tuple[str, list[ToolCall]]:
        content_text = ""
        # Accumulate streamed tool call deltas keyed by index
        accumulated: dict[int, dict[str, str]] = {}

        stream = await self._client.chat.completions.create(stream=True, **kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_text += delta.content
                on_text_chunk(delta.content)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in accumulated:
                        accumulated[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        accumulated[idx]["id"] += tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            accumulated[idx]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            accumulated[idx]["arguments"] += tc_delta.function.arguments

        tool_calls = [
            ToolCall(
                id=accumulated[i]["id"],
                name=accumulated[i]["name"],
                input=json.loads(accumulated[i]["arguments"]) if accumulated[i]["arguments"] else {},
            )
            for i in sorted(accumulated)
        ]
        return content_text, tool_calls


def _to_api_messages(messages: list[Message]) -> list[dict]:
    """Convert internal Anthropic-style messages to OpenAI wire format."""
    result = []
    for msg in messages:
        if msg.role == "assistant":
            if isinstance(msg.content, list):
                # Anthropic-format blocks: extract text and tool_use blocks
                text = ""
                api_tool_calls = []
                for block in msg.content:
                    if block.get("type") == "text":
                        text += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        api_tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        })
                api_msg: dict[str, Any] = {"role": "assistant", "content": text or None}
                if api_tool_calls:
                    api_msg["tool_calls"] = api_tool_calls
                result.append(api_msg)
            else:
                result.append({"role": "assistant", "content": msg.content})
        elif msg.role == "tool":
            # Anthropic-format: list of tool_result blocks → one "tool" message each
            if isinstance(msg.content, list):
                for block in msg.content:
                    if block.get("type") == "tool_result":
                        result.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        })
            else:
                result.append({"role": "tool", "content": msg.content})
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result


def _to_openai_tool(tool: Any) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.schema,
        },
    }
