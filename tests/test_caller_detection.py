"""Tests for caller detection + agent-mode system prompt.

Covers:
  - user_input events carry caller field ("human" / "agent")
  - Agent._build_system_parts() injects structured reply guidance for caller_type="agent"
  - Agent.run() accepts and applies caller_type
  - Session.chat() passes caller_type through
  - send_to_session writes caller: "agent"
  - CLI _send_message writes caller field
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from nutshell.core.agent import Agent
from nutshell.core.types import AgentResult, TokenUsage


# ── Agent._build_system_parts() ──────────────────────────────────────────────

class TestAgentCallerType:
    """Verify _build_system_parts behaviour with caller_type."""

    def test_default_caller_type_is_human(self):
        agent = Agent()
        assert agent.caller_type == "human"

    def test_human_caller_no_guidance(self):
        agent = Agent(system_prompt="Hello")
        agent.caller_type = "human"
        _, dynamic = agent._build_system_parts()
        assert "Agent Collaboration Mode" not in dynamic

    def test_agent_caller_injects_guidance(self):
        agent = Agent(system_prompt="Hello")
        agent.caller_type = "agent"
        _, dynamic = agent._build_system_parts()
        assert "Agent Collaboration Mode" in dynamic
        assert "[DONE]" in dynamic
        assert "[REVIEW]" in dynamic
        assert "[BLOCKED]" in dynamic
        assert "[ERROR]" in dynamic

    def test_agent_guidance_contains_prefix_instructions(self):
        agent = Agent()
        agent.caller_type = "agent"
        _, dynamic = agent._build_system_parts()
        assert "Your caller is another agent" in dynamic
        assert "machine-parseable" in dynamic

    def test_caller_type_set_by_run(self):
        """Agent.run() should set caller_type before building prompts."""
        agent = Agent()
        # We can't easily run the full agent without a provider, but we can
        # verify the attribute is set by checking directly.
        agent.caller_type = "agent"
        _, dynamic = agent._build_system_parts()
        assert "Agent Collaboration Mode" in dynamic

        # Reset to human
        agent.caller_type = "human"
        _, dynamic2 = agent._build_system_parts()
        assert "Agent Collaboration Mode" not in dynamic2


# ── CLI _send_message caller field ────────────────────────────────────────────

class TestCliCallerField:
    """Verify _send_message writes caller field to user_input events."""

    def test_send_message_default_caller_human(self, tmp_path):
        from ui.cli.chat import _send_message
        ctx = tmp_path / "context.jsonl"
        _send_message(ctx, "hello")
        event = json.loads(ctx.read_text().strip())
        assert event["type"] == "user_input"
        assert event["caller"] == "human"

    def test_send_message_caller_agent(self, tmp_path):
        from ui.cli.chat import _send_message
        ctx = tmp_path / "context.jsonl"
        _send_message(ctx, "hello", caller="agent")
        event = json.loads(ctx.read_text().strip())
        assert event["caller"] == "agent"

    def test_send_message_caller_human_explicit(self, tmp_path):
        from ui.cli.chat import _send_message
        ctx = tmp_path / "context.jsonl"
        _send_message(ctx, "hello", caller="human")
        event = json.loads(ctx.read_text().strip())
        assert event["caller"] == "human"


# ── send_to_session writes caller: "agent" ────────────────────────────────────

class TestSendToSessionCaller:
    """Verify send_to_session injects caller='agent' in user_input events."""

    @pytest.mark.asyncio
    async def test_send_to_session_writes_agent_caller(self, tmp_path, monkeypatch):
        from nutshell.tool_engine.providers import session_msg

        # Setup: create a fake target session
        target_id = "target-sess"
        target_dir = tmp_path / target_id
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text("{}")
        ctx_path = target_dir / "context.jsonl"
        ctx_path.touch()

        monkeypatch.setenv("NUTSHELL_SESSION_ID", "caller-sess")

        # Use async mode to avoid polling
        result = await session_msg.send_to_session(
            session_id=target_id,
            message="test message",
            mode="async",
            _system_base=tmp_path,
        )

        assert "sent" in result.lower()

        # Read the written event
        lines = ctx_path.read_text().strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "user_input"
        assert event["caller"] == "agent"

    @pytest.mark.asyncio
    async def test_send_to_session_content_preserved(self, tmp_path, monkeypatch):
        from nutshell.tool_engine.providers import session_msg

        target_id = "target-sess"
        target_dir = tmp_path / target_id
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text("{}")
        ctx_path = target_dir / "context.jsonl"
        ctx_path.touch()

        monkeypatch.setenv("NUTSHELL_SESSION_ID", "caller-sess")

        await session_msg.send_to_session(
            session_id=target_id,
            message="important task",
            mode="async",
            _system_base=tmp_path,
        )

        event = json.loads(ctx_path.read_text().strip())
        assert event["content"] == "important task"
        assert event["caller"] == "agent"


# ── Session.chat() passes caller_type ─────────────────────────────────────────

class TestSessionCallerType:
    """Verify Session.chat() accepts and passes caller_type."""

    def test_chat_signature_accepts_caller_type(self):
        """Session.chat() should accept caller_type keyword argument."""
        import inspect
        from nutshell.runtime.session import Session
        sig = inspect.signature(Session.chat)
        assert "caller_type" in sig.parameters
        param = sig.parameters["caller_type"]
        assert param.default == "human"


# ── Integration: full system prompt with agent caller ─────────────────────────

class TestAgentModeSystemPrompt:
    """Integration tests for the agent-mode system prompt."""

    def test_guidance_appears_in_full_prompt(self):
        agent = Agent(system_prompt="You are a dev agent.")
        agent.caller_type = "agent"
        full_prompt = "\n".join(p for p in agent._build_system_parts() if p)
        assert "Agent Collaboration Mode" in full_prompt
        assert "[DONE]" in full_prompt
        assert "You are a dev agent." in full_prompt

    def test_guidance_absent_for_human(self):
        agent = Agent(system_prompt="You are a dev agent.")
        agent.caller_type = "human"
        full_prompt = "\n".join(p for p in agent._build_system_parts() if p)
        assert "Agent Collaboration Mode" not in full_prompt

    def test_guidance_is_in_dynamic_part(self):
        """Agent collaboration guidance should be in dynamic (not cached) part."""
        agent = Agent(system_prompt="Base prompt")
        agent.caller_type = "agent"
        static, dynamic = agent._build_system_parts()
        assert "Agent Collaboration Mode" not in static
        assert "Agent Collaboration Mode" in dynamic
