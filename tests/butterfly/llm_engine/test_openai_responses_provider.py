"""Unit tests for OpenAIResponsesProvider — conversion + helpers."""
from __future__ import annotations

from types import SimpleNamespace

from butterfly.core.types import Message
from butterfly.llm_engine.providers.openai_responses import (
    OpenAIResponsesProvider,
    _capture_reasoning,
    _convert_assistant,
    _convert_messages,
    _extract_usage_from_obj,
    _tool_to_responses,
)


def test_registry_has_openai_responses():
    from butterfly.llm_engine.registry import _REGISTRY
    assert "openai-responses" in _REGISTRY
    mod, cls = _REGISTRY["openai-responses"]
    assert cls == "OpenAIResponsesProvider"


def test_tool_schema_is_flat_no_inner_function_wrapper():
    class _T:
        def to_api_dict(self):
            return {"name": "search", "description": "search", "input_schema": {"type": "object"}}

    schema = _tool_to_responses(_T())
    assert schema["type"] == "function"
    assert schema["name"] == "search"
    assert "function" not in schema  # flat, not the Chat Completions shape
    assert schema["strict"] is False


def test_convert_assistant_emits_reasoning_before_text():
    msg = Message(
        role="assistant",
        content=[
            {"type": "reasoning", "id": "rs_1", "encrypted_content": "X"},
            {"type": "text", "text": "final"},
        ],
    )
    items = _convert_assistant(msg)
    assert items[0]["type"] == "reasoning"
    assert items[0]["encrypted_content"] == "X"
    assert items[1]["type"] == "message"


def test_convert_messages_user_string_becomes_input_text():
    items = _convert_messages([Message(role="user", content="hi")])
    assert items == [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}]


def test_capture_reasoning_preserves_encrypted_content():
    item = {
        "type": "reasoning",
        "id": "rs_99",
        "summary": [{"type": "summary_text", "text": "s"}],
        "encrypted_content": "OPAQUE",
    }
    out = _capture_reasoning(item)
    assert out == item


def test_capture_reasoning_omits_encrypted_content_when_absent():
    item = {"type": "reasoning", "id": "rs_99", "summary": []}
    out = _capture_reasoning(item)
    assert "encrypted_content" not in out


def test_extract_usage_from_obj_handles_reasoning_and_cache():
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=200,
        input_tokens_details=SimpleNamespace(cached_tokens=20),
        output_tokens_details=SimpleNamespace(reasoning_tokens=100),
    )
    u = _extract_usage_from_obj(usage)
    assert u.input_tokens == 80
    assert u.output_tokens == 200
    assert u.cache_read_tokens == 20
    assert u.reasoning_tokens == 100


def test_extract_usage_from_obj_none_returns_zero():
    u = _extract_usage_from_obj(None)
    assert u.input_tokens == 0
    assert u.output_tokens == 0


def test_consume_extra_blocks_drains():
    p = OpenAIResponsesProvider.__new__(OpenAIResponsesProvider)
    p._pending_reasoning = [{"type": "reasoning", "id": "rs_a"}]
    assert p.consume_extra_blocks() == [{"type": "reasoning", "id": "rs_a"}]
    assert p.consume_extra_blocks() == []
