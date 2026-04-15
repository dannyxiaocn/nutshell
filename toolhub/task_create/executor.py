"""task_create tool — create a new task card in core/tasks/."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from butterfly.session_engine.task_cards import ensure_card, load_card


def _to_iso(value: Any) -> str | None:
    """Accept either a unix-epoch number or an already-ISO string; return ISO or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class TaskCreateExecutor:
    def __init__(self, tasks_dir: str | Path | None = None) -> None:
        self._tasks_dir = Path(tasks_dir) if tasks_dir else None

    async def execute(
        self,
        name: str = "",
        description: str = "",
        interval: float | None = None,
        start_at: Any = None,
        end_at: Any = None,
        **_: Any,
    ) -> str:
        if self._tasks_dir is None:
            return "Error: tasks directory not configured."
        name = (name or "").strip()
        if not name:
            return "Error: 'name' is required."
        if load_card(self._tasks_dir, name) is not None:
            return f"Error: Task '{name}' already exists."
        try:
            ensure_card(
                self._tasks_dir,
                name=name,
                interval=interval,
                description=description or "",
                start_at=_to_iso(start_at),
                end_at=_to_iso(end_at),
            )
        except ValueError as e:
            return f"Error: {e}"
        return f"Created task '{name}'."
