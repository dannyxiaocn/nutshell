"""Unit tests for CodexProvider — request body, error taxonomy, reasoning replay.

These tests don't hit the network; they exercise the pure helpers directly.
"""
from __future__ import annotations

import json

import pytest

from butterfly.core.types import Message, TokenUsage
from butterfly.llm_engine.errors import (
    AuthError,
    BadRequestError,
    ContextWindowExceededError,
    ProviderError,
    RateLimitError,
    ServerError,
)
from butterfly.llm_engine.providers.codex import (
    CodexProvider,
    _build_headers,
    _build_request_body,
    _convert_assistant,
    _convert_messages,
    _extract_usage,
    _parse_retry_after,
    _raise_from_status,
    _raise_stream_error,
    _tool_to_responses_api,
)


def test_default_model_is_gpt5_codex():
    assert CodexProvider.DEFAULT_MODEL == "gpt-5-codex"


def test_build_request_body_thinking_includes_encrypted_content():
    body = _build_request_body(
        "gpt-5-codex",
        "sys",
        [Message(role="user", content="hi")],
        [],
        thinking=True,
        thinking_effort="high",
        prompt_cache_key="conv-123",
    )
    assert body["reasoning"] == {"effort": "high", "summary": "auto"}
    assert body["include"] == ["reasoning.encrypted_content"]
    assert body["prompt_cache_key"] == "conv-123"
    assert body["stream"] is True
    assert body["store"] is False


def test_build_request_body_no_thinking_omits_reasoning_and_include():
    body = _build_request_body(
        "gpt-5-codex", "sys", [Message(role="user", content="hi")], [],
        thinking=False, prompt_cache_key="c",
    )
    assert "reasoning" not in body
    assert "include" not in body


def test_tool_schema_uses_strict_false_not_none():
    class _T:
        def to_api_dict(self):
            return {"name": "echo", "description": "Echo", "input_schema": {"type": "object"}}

    schema = _tool_to_responses_api(_T())
    assert schema["strict"] is False
    assert schema["type"] == "function"
    assert schema["name"] == "echo"


def test_headers_use_codex_cli_originator_and_session_id():
    headers = _build_headers("tok", "acct-1", "conv-uuid")
    assert headers["originator"] == "codex_cli_rs"
    assert headers["ChatGPT-Account-ID"] == "acct-1"
    assert headers["session_id"] == "conv-uuid"
    assert headers["Authorization"] == "Bearer tok"


# ── reasoning replay ─────────────────────────────────────────────────


def test_convert_assistant_replays_reasoning_block_verbatim():
    msg = Message(
        role="assistant",
        content=[
            {
                "type": "reasoning",
                "id": "rs_abc",
                "summary": [{"type": "summary_text", "text": "thinking..."}],
                "encrypted_content": "OPAQUE",
            },
            {"type": "text", "text": "final answer"},
            {"type": "tool_use", "id": "tc-1", "name": "bash", "input": {"cmd": "ls"}},
        ],
    )
    items = _convert_assistant(msg)
    # Order must be: reasoning → text message → function_call
    assert items[0]["type"] == "reasoning"
    assert items[0]["id"] == "rs_abc"
    assert items[0]["encrypted_content"] == "OPAQUE"
    assert items[1]["type"] == "message"
    assert items[2]["type"] == "function_call"
    assert items[2]["call_id"] == "tc-1"


def test_convert_messages_round_trip_user_assistant_tool():
    messages = [
        Message(role="user", content="hello"),
        Message(
            role="assistant",
            content=[
                {"type": "tool_use", "id": "t1", "name": "echo", "input": {"x": 1}},
            ],
        ),
        Message(
            role="tool",
            content=[{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        ),
    ]
    items = _convert_messages(messages)
    kinds = [i.get("type") or i.get("role") for i in items]
    assert kinds == ["user", "function_call", "function_call_output"]


# ── usage extraction ────────────────────────────────────────────────


def test_extract_usage_includes_reasoning_and_cached():
    u = _extract_usage({
        "input_tokens": 100,
        "output_tokens": 200,
        "input_tokens_details": {"cached_tokens": 30},
        "output_tokens_details": {"reasoning_tokens": 120},
    })
    assert u.input_tokens == 70  # 100 - 30 cached
    assert u.output_tokens == 200
    assert u.cache_read_tokens == 30
    assert u.reasoning_tokens == 120


def test_extract_usage_handles_missing_details():
    u = _extract_usage({"input_tokens": 10, "output_tokens": 5})
    assert u == TokenUsage(input_tokens=10, output_tokens=5)


# ── error mapping ───────────────────────────────────────────────────


def test_raise_from_status_maps_401_to_auth_error():
    with pytest.raises(AuthError):
        _raise_from_status(401, "unauthorized")


def test_raise_from_status_maps_400_to_bad_request():
    with pytest.raises(BadRequestError):
        _raise_from_status(400, "bad req")


def test_raise_from_status_maps_429_with_retry_after():
    with pytest.raises(RateLimitError) as exc:
        _raise_from_status(429, "try again in 5s")
    assert exc.value.retry_after == 5.0


def test_raise_from_status_maps_500_to_server_error():
    with pytest.raises(ServerError):
        _raise_from_status(503, "overloaded")


def test_raise_from_status_unknown_raises_generic_provider_error():
    with pytest.raises(ProviderError):
        _raise_from_status(418, "teapot")


def test_raise_stream_error_context_length():
    event = {"type": "response.failed", "response": {"error": {"code": "context_length_exceeded", "message": "too long"}}}
    with pytest.raises(ContextWindowExceededError):
        _raise_stream_error(event)


def test_raise_stream_error_rate_limit():
    event = {"type": "response.failed", "response": {"error": {"code": "rate_limit_exceeded", "message": "retry in 2 minutes"}}}
    with pytest.raises(RateLimitError) as exc:
        _raise_stream_error(event)
    assert exc.value.retry_after == 120.0


def test_raise_stream_error_generic_provider_error():
    event = {"type": "error", "message": "something broke"}
    with pytest.raises(ProviderError):
        _raise_stream_error(event)


# ── retry-after parsing ─────────────────────────────────────────────


@pytest.mark.parametrize("text, expected", [
    ("retry in 5 seconds", 5.0),
    ("retry in 5s", 5.0),
    ("retry in 500ms", 0.5),
    ("wait 2 minutes", 120.0),
    ("try again in 3min", 180.0),
    ("", None),
    ("no hints here", None),
])
def test_parse_retry_after(text, expected):
    assert _parse_retry_after(text) == expected


# ── consume_extra_blocks ────────────────────────────────────────────


def test_consume_extra_blocks_drains_pending_reasoning():
    p = CodexProvider.__new__(CodexProvider)
    p._pending_reasoning = [{"type": "reasoning", "id": "rs_1"}]
    first = p.consume_extra_blocks()
    second = p.consume_extra_blocks()
    assert first == [{"type": "reasoning", "id": "rs_1"}]
    assert second == []


def test_registry_has_codex_oauth():
    from butterfly.llm_engine.registry import _REGISTRY
    assert "codex-oauth" in _REGISTRY
