"""task_update tool — update selected fields on an existing task card."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from butterfly.session_engine.task_cards import load_card, save_card


_UNSET = object()


def _coerce_time(value: Any) -> str | None:
    """Accept unix-epoch number or ISO string; return ISO (or None)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class TaskUpdateExecutor:
    def __init__(self, tasks_dir: str | Path | None = None) -> None:
        self._tasks_dir = Path(tasks_dir) if tasks_dir else None

    async def execute(
        self,
        name: str = "",
        description: Any = _UNSET,
        interval: Any = _UNSET,
        start_at: Any = _UNSET,
        end_at: Any = _UNSET,
        progress: Any = _UNSET,
        comments: Any = _UNSET,
        **_: Any,
    ) -> str:
        if self._tasks_dir is None:
            return "Error: tasks directory not configured."
        name = (name or "").strip()
        if not name:
            return "Error: 'name' is required."

        try:
            card = load_card(self._tasks_dir, name)
        except ValueError as e:
            return f"Error: {e}"
        if card is None:
            return f"Error: Task '{name}' not found."

        changed: list[str] = []
        if description is not _UNSET:
            card.description = description or ""
            changed.append("description")
        if interval is not _UNSET:
            card.interval = interval  # may be None
            changed.append("interval")
        if start_at is not _UNSET:
            card.start_at = _coerce_time(start_at)
            changed.append("start_at")
        if end_at is not _UNSET:
            card.end_at = _coerce_time(end_at)
            changed.append("end_at")
        if progress is not _UNSET:
            card.progress = progress or ""
            changed.append("progress")
        if comments is not _UNSET:
            card.comments = comments or ""
            changed.append("comments")

        if not changed:
            return f"Task '{name}': no fields provided to update."

        save_card(self._tasks_dir, card)
        return f"Updated task '{name}' ({', '.join(changed)})."
