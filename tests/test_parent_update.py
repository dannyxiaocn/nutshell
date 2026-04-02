from __future__ import annotations

import json

import pytest

from nutshell.tool_engine.providers.entity_update import _UPDATES_DIR_NAME, propose_parent_update


@pytest.mark.asyncio
async def test_propose_parent_update_writes_target_parent_record(tmp_path, monkeypatch):
    entity_base = tmp_path / "entity"
    (entity_base / "parent").mkdir(parents=True)
    (entity_base / "parent" / "agent.yaml").write_text("name: parent\n", encoding="utf-8")
    (entity_base / "child").mkdir(parents=True)
    (entity_base / "child" / "agent.yaml").write_text("name: child\nextends: parent\n", encoding="utf-8")
    monkeypatch.setenv("NUTSHELL_ENTITY", "child")
    monkeypatch.setenv("NUTSHELL_SESSION_ID", "test-session")

    result = await propose_parent_update(
        file_path="prompts/system.md",
        content="new parent content",
        reason="Improve inherited system prompt",
        _entity_base=entity_base,
        _updates_base=tmp_path / _UPDATES_DIR_NAME,
    )

    assert "submitted" in result.lower() or "pending" in result.lower()
    files = list((tmp_path / _UPDATES_DIR_NAME).glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["target"] == "parent"
    assert record["parent_entity"] == "parent"
    assert record["file_path"] == "entity/parent/prompts/system.md"
    assert record["content"] == "new parent content"
    assert record["reason"] == "Improve inherited system prompt"
    assert record["session_id"] == "test-session"
    assert record["status"] == "pending"


@pytest.mark.asyncio
async def test_propose_parent_update_rejects_path_outside_parent(tmp_path, monkeypatch):
    entity_base = tmp_path / "entity"
    (entity_base / "parent").mkdir(parents=True)
    (entity_base / "parent" / "agent.yaml").write_text("name: parent\n", encoding="utf-8")
    (entity_base / "child").mkdir(parents=True)
    (entity_base / "child" / "agent.yaml").write_text("name: child\nextends: parent\n", encoding="utf-8")
    monkeypatch.setenv("NUTSHELL_ENTITY", "child")

    result = await propose_parent_update(
        file_path="../sibling/secret.md",
        content="bad",
        reason="test",
        _entity_base=entity_base,
        _updates_base=tmp_path / _UPDATES_DIR_NAME,
    )

    assert "error" in result.lower() or "invalid" in result.lower()
    updates_dir = tmp_path / _UPDATES_DIR_NAME
    assert not updates_dir.exists() or len(list(updates_dir.glob("*.json"))) == 0


@pytest.mark.asyncio
async def test_propose_parent_update_errors_when_parent_missing(tmp_path, monkeypatch):
    entity_base = tmp_path / "entity"
    (entity_base / "child").mkdir(parents=True)
    (entity_base / "child" / "agent.yaml").write_text("name: child\nextends: parent\n", encoding="utf-8")
    monkeypatch.setenv("NUTSHELL_ENTITY", "child")

    result = await propose_parent_update(
        file_path="prompts/system.md",
        content="x",
        reason="test",
        _entity_base=entity_base,
        _updates_base=tmp_path / _UPDATES_DIR_NAME,
    )

    assert "parent entity" in result.lower()
    assert "does not exist" in result.lower()
