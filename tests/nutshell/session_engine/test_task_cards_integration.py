"""Tests for nutshell.session_engine.task_cards module."""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from nutshell.session_engine.task_cards import (
    TaskCard,
    _parse_legacy_md_card,
    clear_all_cards,
    migrate_legacy_task_sources,
    ensure_card,
    has_pending_cards,
    load_all_cards,
    load_due_cards,
    load_card,
    save_card,
)


# ── TaskCard.is_due() ────────────────────────────────────────────────────────


def test_card_is_due_when_never_finished():
    card = TaskCard(name="test", description="do it", interval=600)
    assert card.is_due()


def test_card_not_due_when_finished():
    card = TaskCard(name="test", description="do it", status="finished")
    assert not card.is_due()


def test_card_not_due_when_working():
    card = TaskCard(name="test", description="do it", status="working")
    assert not card.is_due()


def test_card_due_when_interval_elapsed():
    past = (datetime.now() - timedelta(seconds=700)).isoformat()
    card = TaskCard(name="test", description="do it", interval=600, last_finished_at=past)
    assert card.is_due()


def test_card_due_when_interval_elapsed_with_timezone_aware_timestamp():
    past = (datetime.now().astimezone() - timedelta(seconds=700)).isoformat()
    card = TaskCard(name="test", description="do it", interval=600, last_finished_at=past)
    assert card.is_due()


def test_card_not_due_when_interval_not_elapsed():
    recent = (datetime.now() - timedelta(seconds=100)).isoformat()
    card = TaskCard(name="test", description="do it", interval=600, last_finished_at=recent)
    assert not card.is_due()


def test_oneshot_card_not_due_after_finished():
    """One-shot cards (interval=None) should not be due after first finish."""
    card = TaskCard(
        name="test", description="do it", interval=None,
        status="finished", last_finished_at=datetime.now().isoformat(),
    )
    assert not card.is_due()


def test_oneshot_card_due_when_never_finished():
    card = TaskCard(name="test", description="do it", interval=None)
    assert card.is_due()


# ── mark_working / mark_finished ─────────────────────────────────────────────


def test_mark_working():
    card = TaskCard(name="test", description="x")
    card.mark_working()
    assert card.status == "working"
    assert card.last_started_at is not None


def test_mark_finished_oneshot():
    card = TaskCard(name="test", description="x", interval=None)
    card.mark_finished()
    assert card.status == "finished"
    assert card.last_finished_at is not None


def test_mark_finished_recurring():
    card = TaskCard(name="test", description="x", interval=600)
    card.mark_finished()
    assert card.status == "paused"
    assert card.last_finished_at is not None


def test_mark_paused():
    card = TaskCard(name="test", description="x", status="working")
    card.mark_paused()
    assert card.status == "paused"


# ── Serialization round-trip ─────────────────────────────────────────────────


def test_serialize_and_parse_roundtrip(tmp_path):
    card = TaskCard(
        name="my_task",
        description="Do something important",
        interval=3600,
        status="paused",
        created_at="2026-04-08T12:00:00",
    )
    path = save_card(tmp_path, card)
    assert path == tmp_path / "my_task.json"
    assert path.exists()

    loaded = load_card(tmp_path, "my_task")
    assert loaded is not None
    assert loaded.name == "my_task"
    assert loaded.description == "Do something important"
    assert loaded.interval == 3600
    assert loaded.status == "paused"
    assert loaded.created_at == "2026-04-08T12:00:00"


def test_to_dict_from_dict_roundtrip():
    card = TaskCard(
        name="rt",
        description="round-trip test",
        interval=1800,
        status="paused",
        comments="some notes",
        progress="50%",
    )
    d = card.to_dict()
    restored = TaskCard.from_dict(d)
    assert restored.name == "rt"
    assert restored.description == "round-trip test"
    assert restored.interval == 1800
    assert restored.comments == "some notes"
    assert restored.progress == "50%"


def test_from_dict_backward_compat_last_run_at():
    """from_dict maps legacy last_run_at to last_finished_at."""
    d = {"name": "old", "last_run_at": "2026-01-01T00:00:00"}
    card = TaskCard.from_dict(d)
    assert card.last_finished_at == "2026-01-01T00:00:00"


# ── Directory operations ──────────────────────────────────────────────────────


def test_load_all_cards(tmp_path):
    save_card(tmp_path, TaskCard(name="a", description="task a"))
    save_card(tmp_path, TaskCard(name="b", description="task b", status="finished"))
    cards = load_all_cards(tmp_path)
    assert len(cards) == 2
    names = {c.name for c in cards}
    assert names == {"a", "b"}


def test_load_all_cards_empty_dir(tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    assert load_all_cards(tasks_dir) == []


def test_load_all_cards_nonexistent_dir(tmp_path):
    assert load_all_cards(tmp_path / "nonexistent") == []


def test_load_due_cards(tmp_path):
    save_card(tmp_path, TaskCard(name="due", description="x", interval=600))
    save_card(tmp_path, TaskCard(name="done", description="y", status="finished"))
    save_card(tmp_path, TaskCard(name="busy", description="z", status="working"))
    due = load_due_cards(tmp_path)
    assert len(due) == 1
    assert due[0].name == "due"


def test_has_pending_cards(tmp_path):
    assert not has_pending_cards(tmp_path)
    save_card(tmp_path, TaskCard(name="t", description="x"))
    assert has_pending_cards(tmp_path)


def test_clear_all_cards(tmp_path):
    save_card(tmp_path, TaskCard(name="a", description="x"))
    save_card(tmp_path, TaskCard(name="b", description="y", interval=600))
    clear_all_cards(tmp_path)
    cards = load_all_cards(tmp_path)
    assert all(c.status == "finished" for c in cards)


# ── Migration ─────────────────────────────────────────────────────────────────


def test_migrate_legacy_task_sources_with_tasks_md(tmp_path):
    session_dir = tmp_path / "session"
    core_dir = session_dir / "core"
    core_dir.mkdir(parents=True)
    tasks_md = core_dir / "tasks.md"
    tasks_md.write_text("- [ ] do something\n- [ ] do another thing\n", encoding="utf-8")

    migrate_legacy_task_sources(session_dir)

    assert not tasks_md.exists()
    tasks_dir = core_dir / "tasks"
    cards = load_all_cards(tasks_dir)
    assert len(cards) == 1
    assert cards[0].name == "migrated_task"
    assert "do something" in cards[0].description
    assert cards[0].interval is None


def test_migrate_legacy_task_sources_empty_tasks_md(tmp_path):
    session_dir = tmp_path / "session"
    core_dir = session_dir / "core"
    core_dir.mkdir(parents=True)
    tasks_md = core_dir / "tasks.md"
    tasks_md.write_text("", encoding="utf-8")

    migrate_legacy_task_sources(session_dir)

    assert not tasks_md.exists()
    tasks_dir = core_dir / "tasks"
    assert tasks_dir.is_dir()
    assert load_all_cards(tasks_dir) == []


def test_migrate_noop_when_no_tasks_md(tmp_path):
    session_dir = tmp_path / "session"
    core_dir = session_dir / "core"
    core_dir.mkdir(parents=True)
    migrate_legacy_task_sources(session_dir)
    assert not (core_dir / "tasks").exists()


def test_migrate_skips_when_cards_exist(tmp_path):
    session_dir = tmp_path / "session"
    core_dir = session_dir / "core"
    core_dir.mkdir(parents=True)
    tasks_md = core_dir / "tasks.md"
    tasks_md.write_text("old content", encoding="utf-8")
    tasks_dir = core_dir / "tasks"
    save_card(tasks_dir, TaskCard(name="existing", description="already here"))

    migrate_legacy_task_sources(session_dir)

    cards = load_all_cards(tasks_dir)
    names = {c.name for c in cards}
    assert "existing" in names
    assert "migrated_task" not in names


# ── Legacy .md card parsing ──────────────────────────────────────────────────


def test_parse_legacy_md_card_with_frontmatter(tmp_path):
    path = tmp_path / "old_task.md"
    path.write_text(
        "---\nstatus: running\ninterval: 3600\nlast_run_at: 2026-01-01T00:00:00\n---\n\nDo stuff\n",
        encoding="utf-8",
    )
    card = _parse_legacy_md_card(path)
    assert card.name == "old_task"
    assert card.status == "working"  # "running" maps to "working"
    assert card.interval == 3600
    # YAML may parse datetime strings as datetime objects
    assert str(card.last_finished_at).startswith("2026-01-01")
    assert card.description == "Do stuff"


def test_parse_legacy_md_card_without_frontmatter(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("Just a plain task\n", encoding="utf-8")
    card = _parse_legacy_md_card(path)
    assert card.name == "plain"
    assert card.description == "Just a plain task"
    assert card.status == "paused"  # "pending" maps to "paused"


def test_load_all_cards_includes_legacy_md(tmp_path):
    """load_all_cards loads both .json and legacy .md cards."""
    save_card(tmp_path, TaskCard(name="modern", description="json card"))
    (tmp_path / "old.md").write_text("---\nstatus: pending\n---\n\nLegacy task\n", encoding="utf-8")
    cards = load_all_cards(tmp_path)
    names = {c.name for c in cards}
    assert "modern" in names
    assert "old" in names


# ── ensure_card ──────────────────────────────────────────────────────────────


def test_ensure_card_creates(tmp_path):
    card = ensure_card(tmp_path, name="duty", interval=3600, description="Duty task")
    assert card.name == "duty"
    assert card.interval == 3600
    assert card.status == "paused"
    assert (tmp_path / "duty.json").exists()


def test_ensure_card_idempotent(tmp_path):
    card1 = ensure_card(tmp_path, name="duty", interval=3600)
    card1.last_finished_at = "2026-04-08T00:00:00"
    save_card(tmp_path, card1)

    card2 = ensure_card(tmp_path, name="duty", interval=7200)
    assert card2.last_finished_at == "2026-04-08T00:00:00"
    assert card2.interval == 3600  # original preserved
