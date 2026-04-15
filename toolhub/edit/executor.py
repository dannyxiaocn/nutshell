"""edit tool — exact-string replacement on a file."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from butterfly.tool_engine.executor.base import BaseExecutor


class EditExecutor(BaseExecutor):
    """Executor for the built-in edit tool."""

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
        old_string: str = kwargs["old_string"]
        new_string: str = kwargs["new_string"]
        replace_all = bool(kwargs.get("replace_all", False))

        if old_string == new_string:
            return "Error: old_string and new_string are identical; no change."

        resolved = self._resolve(path_arg)
        if not resolved.exists() or not resolved.is_file():
            return f"Error: File not found: {path_arg}"

        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            return f"Error: Failed to read {path_arg}: {exc}"

        text = raw.decode("utf-8", errors="replace")
        count = text.count(old_string)
        if count == 0:
            return f"Error: old_string not found in {path_arg}"
        if count > 1 and not replace_all:
            return (
                f"Error: old_string appears {count} times in {path_arg}. "
                f"Pass replace_all=true or supply more context."
            )

        if replace_all:
            new_text = text.replace(old_string, new_string)
            replacements = count
        else:
            new_text = text.replace(old_string, new_string, 1)
            replacements = 1

        data = new_text.encode("utf-8")
        try:
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

        noun = "occurrence" if replacements == 1 else "occurrences"
        return f"Replaced {replacements} {noun} in {path_arg}."
