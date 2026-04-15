"""tool_output — fetch the output of a backgrounded tool call.

Reads the output file pointed to by `panel/<tid>.json#output_file`. Default
mode returns the full accumulated output; `delta=true` returns only the bytes
added since the last fetch (tracked via `last_delivered_bytes` on the panel
entry, which is the same field progress-heartbeats advance).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from butterfly.session_engine.panel import load_entry, save_entry


class ToolOutputExecutor:
    """Fetch output of a background task by tid. Context-injected with panel_dir."""

    def __init__(self, panel_dir: Path | None = None) -> None:
        self._panel_dir = panel_dir

    async def execute(self, **kwargs: Any) -> str:
        task_id = kwargs.get("task_id")
        if not task_id:
            return "Error: task_id is required."
        if self._panel_dir is None:
            return "Error: tool_output is not wired to a session panel directory."

        entry = load_entry(self._panel_dir, task_id)
        if entry is None:
            return f"Error: no panel entry with task_id '{task_id}'."

        delta_mode = bool(kwargs.get("delta", False))

        if not entry.output_file:
            return f"Task {task_id} has no output file yet. Status: {entry.status}."

        output_path = Path(entry.output_file)
        if not output_path.exists():
            return f"Task {task_id} output file is missing ({output_path}). Status: {entry.status}."

        try:
            data = output_path.read_bytes()
        except OSError as exc:
            return f"Error reading output file for {task_id}: {exc}"

        if delta_mode:
            start = entry.last_delivered_bytes
            chunk = data[start:]
            entry.last_delivered_bytes = len(data)
            save_entry(self._panel_dir, entry)
            text = chunk.decode(errors="replace")
        else:
            text = data.decode(errors="replace")

        footer = (
            f"\n[task {task_id} status={entry.status} exit={entry.exit_code} "
            f"bytes={entry.output_bytes}"
            + (" delta-mode" if delta_mode else "")
            + "]"
        )
        return (text.rstrip() + footer) if text else footer.lstrip()
