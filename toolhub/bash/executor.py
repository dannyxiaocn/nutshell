"""Bash toolhub entry — re-exports the canonical implementation.

The real executor lives in `butterfly/tool_engine/executor/terminal/bash_terminal.py`.
This file exists solely so the conventional `toolhub/<name>/executor.py` discovery
path in `ToolLoader._create_executor` can find `BashExecutor`.
"""
from butterfly.tool_engine.executor.terminal.bash_terminal import (  # noqa: F401
    BashExecutor,
    create_bash_tool,
)
