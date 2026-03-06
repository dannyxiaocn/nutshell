"""Example 05: Load an agent from entity/ folder using AgentLoader.

Demonstrates Layer 3 (entity/) + AgentLoader working together.
The agent's system prompt, tools, and skills all come from external files
under entity/core_agent/ — no hardcoded strings in Python.
"""
import asyncio
from pathlib import Path

from nutshell import AgentLoader, AnthropicProvider

REPO_ROOT = Path(__file__).parent.parent
AGENT_DIR = REPO_ROOT / "entity" / "core_agent"


def build_agent():
    return AgentLoader(impl_registry={
        "echo": lambda text: text,
    }).load(AGENT_DIR)


async def main():
    agent = build_agent()

    print("=== Entity Agent Demo ===")
    print(f"Prompt : {AGENT_DIR / 'prompts' / 'system.md'}")
    print(f"Tools  : {[t.name for t in agent.tools]}")
    print(f"Skills : {[s.name for s in agent.skills]}")
    print()

    result = await agent.run('Please echo the text "Hello from entity layer!"')
    print("Response:", result.content)
    if result.tool_calls:
        print(f"Tool calls: {[tc.name for tc in result.tool_calls]}")


if __name__ == "__main__":
    asyncio.run(main())
