from __future__ import annotations
from pathlib import Path
from typing import Any

from nutshell.tool_engine.executor.base import BaseExecutor


class HttpExecutor(BaseExecutor):
    """PLACEHOLDER: executor for HTTP-backed tools."""

    @classmethod
    def can_handle(cls, tool_name: str, tool_path: Path | None) -> bool:
        return False

    async def execute(self, **kwargs: Any) -> str:
        raise NotImplementedError("HttpExecutor is not yet implemented.")
