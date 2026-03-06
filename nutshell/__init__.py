"""Nutshell — a minimal Python Agent library."""

from nutshell.core.agent import Agent
from nutshell.core.instance import Instance
from nutshell.abstract.provider import Provider
from nutshell.providers.anthropic import AnthropicProvider
from nutshell.core.skill import Skill
from nutshell.core.tool import Tool, tool
from nutshell.core.types import AgentResult, Message, ToolCall

# Abstract base classes
from nutshell.abstract.agent import BaseAgent
from nutshell.abstract.tool import BaseTool
from nutshell.abstract.skill import BaseSkill
from nutshell.abstract.loader import BaseLoader

# External file loaders
from nutshell.loaders.prompt import PromptLoader
from nutshell.loaders.tool import ToolLoader
from nutshell.loaders.skill import SkillLoader
from nutshell.loaders.agent import AgentLoader

__all__ = [
    # Core
    "Agent",
    "Instance",
    "Provider",
    "AnthropicProvider",
    "Skill",
    "Tool",
    "tool",
    "AgentResult",
    "Message",
    "ToolCall",
    # Abstract base classes
    "BaseAgent",
    "BaseTool",
    "BaseSkill",
    "BaseLoader",
    # Loaders
    "PromptLoader",
    "ToolLoader",
    "SkillLoader",
    "AgentLoader",
]
