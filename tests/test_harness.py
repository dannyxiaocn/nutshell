"""Tests for the harness feedback system.

Covers:
  - AgentResult.iterations field (types.py)
  - Agent.run() iteration counting (agent.py)
  - Session._write_harness_snapshot() (session.py)
"""

import pytest
from unittest.mock import AsyncMock
from pathlib import Path

from nutshell.core.agent import Agent
from nutshell.core.provider import Provider
from nutshell.core.tool import tool
from nutshell.core.types import AgentResult, TokenUsage, ToolCall


# ── Helpers ────────────────────────────────────────────────────────


class MockProvider(Provider):
    """A mock provider for testing without real API calls."""

    def __init__(self, responses):
        self._responses = iter(responses)

    async def complete(self, messages, tools, system_prompt, model, *,
                       on_text_chunk=None, cache_system_prefix="",
                       cache_last_human_turn=False, thinking: bool = False, thinking_budget: int = 8000):
        r = next(self._responses)
        return (r[0], r[1], r[2] if len(r) > 2 else TokenUsage())


# ── types.py — AgentResult.iterations ──────────────────────────────


def test_agent_result_iterations_default():
    """iterations defaults to 0."""
    result = AgentResult(content="hello")
    assert result.iterations == 0


def test_agent_result_iterations_explicit():
    """iterations can be set explicitly."""
    result = AgentResult(content="hello", iterations=5)
    assert result.iterations == 5


# ── agent.py — iteration counting ─────────────────────────────────


@pytest.mark.asyncio
async def test_single_iteration_no_tools():
    """A simple completion with no tool calls = 1 iteration."""
    provider = MockProvider([("Hello!", [])])
    agent = Agent(provider=provider)
    result = await agent.run("Hi")
    assert result.iterations == 1


@pytest.mark.asyncio
async def test_multiple_iterations_with_tool_loop():
    """A tool-call loop of N rounds = N iterations."""
    calc_call = ToolCall(id="1", name="add", input={"a": 1, "b": 2})

    provider = MockProvider([
        ("", [calc_call]),                # iteration 1: tool call
        ("", [calc_call]),                # iteration 2: tool call again
        ("The answer is 3.", []),          # iteration 3: final answer
    ])

    @tool(description="Add numbers")
    def add(a: int, b: int) -> int:
        return a + b

    agent = Agent(provider=provider, tools=[add])
    result = await agent.run("What is 1 + 2?")
    assert result.iterations == 3
    assert result.content == "The answer is 3."


@pytest.mark.asyncio
async def test_single_tool_call_two_iterations():
    """One tool call = 2 iterations (call + final answer)."""
    calc_call = ToolCall(id="1", name="add", input={"a": 5, "b": 3})

    provider = MockProvider([
        ("", [calc_call]),
        ("8", []),
    ])

    @tool(description="Add numbers")
    def add(a: int, b: int) -> int:
        return a + b

    agent = Agent(provider=provider, tools=[add])
    result = await agent.run("5 + 3?")
    assert result.iterations == 2


@pytest.mark.asyncio
async def test_iterations_with_token_usage():
    """iterations is set alongside usage."""
    usage = TokenUsage(input_tokens=100, output_tokens=50)
    provider = MockProvider([("ok", [], usage)])
    agent = Agent(provider=provider)
    result = await agent.run("test")
    assert result.iterations == 1
    assert result.usage.input_tokens == 100


# ── session.py — _write_harness_snapshot ──────────────────────────


@pytest.mark.asyncio
async def test_write_harness_snapshot_creates_file(tmp_path):
    """_write_harness_snapshot writes core/memory/harness.md."""
    from nutshell.runtime.session import Session

    provider = MockProvider([("ok", [], TokenUsage(input_tokens=200, output_tokens=80))])
    agent = Agent(provider=provider)

    session = Session(
        agent,
        session_id="test-harness",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    result = await session.chat("hello")

    harness_path = session.core_dir / "memory" / "harness.md"
    assert harness_path.exists(), "harness.md should be created"

    content = harness_path.read_text()
    assert "triggered_by | user" in content
    assert "iterations | 1" in content
    assert "tool_calls | 0" in content
    assert "input_tokens | 200" in content
    assert "output_tokens | 80" in content
    assert "total_tokens | 280" in content
    assert "history_turns | 2" in content  # user + assistant


@pytest.mark.asyncio
async def test_write_harness_snapshot_with_tools(tmp_path):
    """harness.md records tool call info correctly."""
    from nutshell.runtime.session import Session

    calc_call = ToolCall(id="1", name="bash", input={"command": "echo hi"})

    provider = MockProvider([
        ("", [calc_call], TokenUsage(input_tokens=100, output_tokens=30)),
        ("done", [], TokenUsage(input_tokens=150, output_tokens=40)),
    ])

    @tool(description="Run shell")
    def bash(command: str) -> str:
        return "hi"

    agent = Agent(provider=provider, tools=[bash])

    session = Session(
        agent,
        session_id="test-harness-tools",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    result = await session.chat("run echo")

    harness_path = session.core_dir / "memory" / "harness.md"
    content = harness_path.read_text()
    assert "iterations | 2" in content
    assert "tool_calls | 1" in content
    assert "bash" in content
    assert "input_tokens | 250" in content   # 100 + 150
    assert "output_tokens | 70" in content   # 30 + 40


@pytest.mark.asyncio
async def test_harness_snapshot_heartbeat(tmp_path):
    """tick() writes harness.md with triggered_by=heartbeat."""
    from nutshell.runtime.session import Session

    provider = MockProvider([("ok done", [])])
    agent = Agent(provider=provider)

    session = Session(
        agent,
        session_id="test-harness-hb",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    # Write a task so tick() fires
    session.tasks_path.write_text("- do something", encoding="utf-8")

    result = await session.tick()
    assert result is not None

    harness_path = session.core_dir / "memory" / "harness.md"
    assert harness_path.exists()
    content = harness_path.read_text()
    assert "triggered_by | heartbeat" in content
    assert "iterations | 1" in content


@pytest.mark.asyncio
async def test_harness_snapshot_overwrites_previous(tmp_path):
    """Each turn overwrites harness.md (latest turn only)."""
    from nutshell.runtime.session import Session

    provider = MockProvider([
        ("first", [], TokenUsage(input_tokens=100, output_tokens=10)),
        ("second", [], TokenUsage(input_tokens=200, output_tokens=20)),
    ])
    agent = Agent(provider=provider)

    session = Session(
        agent,
        session_id="test-harness-overwrite",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    await session.chat("first msg")
    harness_path = session.core_dir / "memory" / "harness.md"
    content1 = harness_path.read_text()
    assert "input_tokens | 100" in content1

    await session.chat("second msg")
    content2 = harness_path.read_text()
    assert "input_tokens | 200" in content2
    assert "input_tokens | 100" not in content2  # overwritten


@pytest.mark.asyncio
async def test_harness_injected_as_memory_layer(tmp_path):
    """harness.md is loaded as a memory layer on next activation."""
    from nutshell.runtime.session import Session

    responses = [
        ("first", [], TokenUsage(input_tokens=100, output_tokens=10)),
        ("second", [], TokenUsage(input_tokens=200, output_tokens=20)),
    ]
    provider = MockProvider(responses)
    agent = Agent(provider=provider)

    session = Session(
        agent,
        session_id="test-harness-inject",
        base_dir=tmp_path / "sessions",
        system_base=tmp_path / "_sessions",
    )

    # First chat creates harness.md
    await session.chat("hello")

    # Second chat triggers _load_session_capabilities which reads memory layers
    # The harness.md should be among them
    await session.chat("world")

    # Check that agent has a harness memory layer
    layer_names = [name for name, _ in agent.memory_layers]
    assert "harness" in layer_names, f"Expected 'harness' in memory layers, got: {layer_names}"
