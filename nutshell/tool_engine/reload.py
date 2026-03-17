"""reload_capabilities built-in tool factory.

Avoids circular imports by depending only on a Protocol, not on
the concrete Session class.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from nutshell.core.tool import Tool

if TYPE_CHECKING:
    pass


class _ReloadTarget(Protocol):
    def _load_session_capabilities(self) -> None: ...


def create_reload_tool(session: _ReloadTarget) -> Tool:
    """Return a Tool that triggers capability hot-reload for *session*."""

    def _reload() -> str:
        session._load_session_capabilities()
        return "Capabilities reloaded."

    return Tool(
        name="reload_capabilities",
        description=(
            "Reload tools and skills from core/ without restarting the session. "
            "Call after creating or modifying a tool (.json + .sh) or skill (SKILL.md) "
            "to make the changes available in the current conversation."
        ),
        func=_reload,
        schema={"type": "object", "properties": {}, "required": []},
    )
