from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from nutshell.session_engine.task_cards import (
    TaskCard,
    _parse_legacy_md_card,
    ensure_card,
    load_all_cards,
    migrate_legacy_task_sources,
    save_card,
)


class TaskCardsUnitTests(unittest.TestCase):
    def test_is_due_handles_timezone_aware_last_finished(self) -> None:
        last = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        card = TaskCard(name="duty", description="ping", interval=60, last_finished_at=last)
        self.assertTrue(card.is_due())

    def test_parse_legacy_md_card_handles_non_mapping_frontmatter(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "weird.md"
            path.write_text("---\n- not\n- a\n- mapping\n---\n\nbody", encoding="utf-8")
            card = _parse_legacy_md_card(path)

        self.assertEqual(card.name, "weird")
        self.assertEqual(card.status, "paused")  # "pending" maps to "paused"
        self.assertEqual(card.description, "body")

    def test_migrate_legacy_task_sources_preserves_existing_cards(self) -> None:
        with TemporaryDirectory() as td:
            session_dir = Path(td) / "session"
            core_dir = session_dir / "core"
            core_dir.mkdir(parents=True)
            save_card(core_dir / "tasks", TaskCard(name="existing", description="already there"))
            (core_dir / "tasks.md").write_text("legacy content", encoding="utf-8")

            migrate_legacy_task_sources(session_dir)
            cards = load_all_cards(core_dir / "tasks")

        self.assertEqual([card.name for card in cards], ["existing"])

    def test_ensure_card_keeps_existing(self) -> None:
        with TemporaryDirectory() as td:
            tasks_dir = Path(td)
            created = ensure_card(tasks_dir, name="duty", interval=60, description="first")
            # Modify and save
            created.description = "customized"
            save_card(tasks_dir, created)

            loaded = ensure_card(tasks_dir, name="duty", interval=120, description="second")

        self.assertEqual(loaded.description, "customized")
        self.assertEqual(loaded.interval, 60)
