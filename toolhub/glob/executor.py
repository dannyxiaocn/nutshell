"""Glob tool — find files by pattern, sorted by mtime (newest first)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from butterfly.tool_engine.executor.base import BaseExecutor

_MAX_RESULTS = 500


class GlobExecutor(BaseExecutor):
    """Executor for the built-in glob tool."""

    def __init__(self, workdir: str | None = None) -> None:
        self._workdir = workdir

    def _resolve_root(self, path: str | None) -> Path:
        if path:
            p = Path(path)
            if not p.is_absolute() and self._workdir:
                p = Path(self._workdir) / p
            return p
        if self._workdir:
            return Path(self._workdir)
        return Path.cwd()

    async def execute(self, **kwargs: Any) -> str:
        pattern: str = kwargs["pattern"]
        path = kwargs.get("path")
        root = self._resolve_root(path)

        if not root.is_dir():
            return f"Error: search root is not a directory: {root}"

        # Path-aware pattern vs filename-only pattern
        # If pattern contains a `/`, the caller cares about the path layout —
        # use Path.glob so the pattern is anchored at root. Otherwise they
        # want filename matching at any depth — use rglob.
        try:
            if "/" in pattern:
                matches_iter = root.glob(pattern)
            else:
                matches_iter = root.rglob(pattern)
            matches = [p for p in matches_iter if p.is_file()]
        except (ValueError, OSError) as exc:
            return f"Error: glob failed: {exc}"

        if not matches:
            return f"No files matched '{pattern}' under {root}."

        # Sort by mtime descending (newest first). Skip entries that vanish.
        def _mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0.0

        matches.sort(key=_mtime, reverse=True)

        total = len(matches)
        shown = matches[:_MAX_RESULTS]

        lines: list[str] = []
        for p in shown:
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            lines.append(str(rel))

        if total > _MAX_RESULTS:
            lines.append(f"[truncated at {_MAX_RESULTS} of {total} total matches]")

        return "\n".join(lines)
