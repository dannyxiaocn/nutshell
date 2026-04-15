"""Toolhub entry point for the `session_shell` tool.

The real implementation lives in
`butterfly/tool_engine/executor/terminal/session_shell.py`; this module
re-exports `SessionShellExecutor` so `ToolLoader._load_executor_module` can
import it via the conventional `toolhub/<name>/executor.py` path.
"""
from __future__ import annotations

from butterfly.tool_engine.executor.terminal.session_shell import (  # noqa: F401
    SessionShellExecutor,
)

__all__ = ["SessionShellExecutor"]
