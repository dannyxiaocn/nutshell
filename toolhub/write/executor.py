"""write tool — atomic whole-file write with parent-dir creation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from butterfly.tool_engine.executor.base import BaseExecutor


class WriteExecutor(BaseExecutor):
    """Executor for the built-in write tool."""

    def __init__(self, workdir: str | None = None) -> None:
        self._workdir = workdir

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        base = Path(self._workdir) if self._workdir else Path.cwd()
        return base / p

    async def execute(self, **kwargs: Any) -> str:
        path_arg: str = kwargs["path"]
        content: str = kwargs["content"]

        resolved = self._resolve(path_arg)
        data = content.encode("utf-8")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
            with open(tmp_path, "wb") as fh:
                fh.write(data)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, resolved)
        except OSError as exc:
            return f"Error: Failed to write {path_arg}: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            return f"Error: Failed to write {path_arg}: {exc}"

        return f"Wrote {len(data)} bytes to {path_arg}."
