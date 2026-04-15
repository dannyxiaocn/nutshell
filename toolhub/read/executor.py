"""read tool — paginated file read with per-line trimming and total-char cap."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from butterfly.tool_engine.executor.base import BaseExecutor


_MAX_OUTPUT_CHARS = 100_000
_DEFAULT_LIMIT = 2000
_DEFAULT_OFFSET = 1


class ReadExecutor(BaseExecutor):
    """Executor for the built-in read tool."""

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
        offset = int(kwargs.get("offset") or _DEFAULT_OFFSET)
        limit = int(kwargs.get("limit") or _DEFAULT_LIMIT)
        if offset < 1:
            offset = 1
        if limit < 1:
            limit = _DEFAULT_LIMIT

        resolved = self._resolve(path_arg)
        if not resolved.exists() or not resolved.is_file():
            return f"Error: File not found: {path_arg}"

        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            return f"Error: Failed to read {path_arg}: {exc}"

        text = raw.decode("utf-8", errors="replace")
        # Splitlines preserves blank lines but drops trailing newline semantics;
        # that's fine for display-oriented output.
        all_lines = text.splitlines()
        total_lines = len(all_lines)

        start_idx = offset - 1
        if start_idx >= total_lines:
            return (
                f"[read {len(raw)} bytes, lines {offset}-{offset - 1} of {total_lines}]"
            )
        end_idx = min(start_idx + limit, total_lines)
        selected = all_lines[start_idx:end_idx]
        # Strip trailing whitespace from each line (preserves blank lines).
        cleaned = [line.rstrip() for line in selected]

        body = "\n".join(cleaned)
        footer = f"[read {len(raw)} bytes, lines {start_idx + 1}-{end_idx} of {total_lines}]"

        if len(body) > _MAX_OUTPUT_CHARS:
            body = body[-_MAX_OUTPUT_CHARS:]
            return f"{body}\n[truncated to last {_MAX_OUTPUT_CHARS} chars]\n{footer}"
        return f"{body}\n{footer}" if body else footer
