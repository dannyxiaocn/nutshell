import json

import pytest

from nutshell.core.agent import Agent
from nutshell.core.types import AgentResult, TokenUsage
from nutshell.runtime.session import Session


class _Provider:
    async def complete(self, messages, tools, system_prompt, model, **kwargs):
        return ("ok", [], TokenUsage())


@pytest.mark.asyncio
async def test_write_harness_snapshot_writes_audit_and_harness(tmp_path):
    agent = Agent(provider=_Provider())
    session = Session(
        agent,
        session_id="test-runtime-harness-audit",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    result = AgentResult(
        content="ok",
        tool_calls=[],
        iterations=3,
        usage=TokenUsage(input_tokens=12, output_tokens=8),
    )

    session._write_harness_snapshot(result, "user")

    harness_path = session.core_dir / "memory" / "harness.md"
    audit_path = session.core_dir / "audit.jsonl"

    assert harness_path.exists()
    harness = harness_path.read_text(encoding="utf-8")
    assert "triggered_by | user" in harness
    assert "iterations | 3" in harness
    assert "input_tokens | 12" in harness
    assert "output_tokens | 8" in harness
    assert "total_tokens | 20" in harness

    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["session_id"] == "test-runtime-harness-audit"
    assert entry["triggered_by"] == "user"
    assert entry["iterations"] == 3
    assert entry["tool_calls"] == 0
    assert entry["tools_used"] == []
    assert entry["input_tokens"] == 12
    assert entry["output_tokens"] == 8
    assert entry["total_tokens"] == 20
    assert "model" in entry
    assert "provider" in entry
    assert "ts" in entry
