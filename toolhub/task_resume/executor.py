"""task_resume tool — return a paused task card to pending."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from butterfly.session_engine.task_cards import load_card, save_card


class TaskResumeExecutor:
    def __init__(self, tasks_dir: str | Path | None = None) -> None:
        self._tasks_dir = Path(tasks_dir) if tasks_dir else None

    async def execute(self, name: str = "", **_: Any) -> str:
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
        card.mark_pending()
        save_card(self._tasks_dir, card)
        return f"Task '{name}' resumed."
