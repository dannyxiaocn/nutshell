"""task_list tool — list all task cards, optionally filtered by status."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from butterfly.session_engine.task_cards import load_all_cards


class TaskListExecutor:
    def __init__(self, tasks_dir: str | Path | None = None) -> None:
        self._tasks_dir = Path(tasks_dir) if tasks_dir else None

    async def execute(self, status: str | None = None, **_: Any) -> str:
        if self._tasks_dir is None:
            return "Error: tasks directory not configured."
        cards = load_all_cards(self._tasks_dir)
        if status:
            want = str(status).strip().lower()
            cards = [c for c in cards if c.status == want]
        if not cards:
            return "No task cards found." if not status else f"No task cards with status '{status}'."
        lines = []
        for c in cards:
            # `interval is None` means one-shot; 0 is technically valid and
            # should NOT be mislabelled as one-shot (it would fire every tick
            # by design, and the schema now rejects it at ingress — but we
            # keep the display honest in case old cards exist on disk).
            interval_str = f"{c.interval}s" if c.interval is not None else "one-shot"
            last = c.last_finished_at or c.last_started_at or "never"
            lines.append(f"{c.name} [{c.status}] interval={interval_str} last={last}")
        return "\n".join(lines)
