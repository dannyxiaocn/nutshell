from __future__ import annotations

from pathlib import Path

import yaml

from porter_test_support import repo_root_from


REPO_ROOT = repo_root_from(Path(__file__))
ENTITY_ROOT = REPO_ROOT / "entity"


def _manifest(entity_name: str) -> dict:
    return yaml.safe_load((ENTITY_ROOT / entity_name / "agent.yaml").read_text(encoding="utf-8")) or {}


def test_porters_manifest_sets_persistent_porter_defaults():
    manifest = _manifest("porters")
    params = manifest["params"]

    assert manifest["extends"] == "nutshell_dev_codex"
    assert params["session_type"] == "persistent"
    assert params["heartbeat_interval"] == 10800
    assert "ready-" in params["default_task"]
    assert "wip-" in params["default_task"]
    assert "tests/porter_system/" in params["default_task"]


def test_porters_heartbeat_prompt_enforces_ready_branch_workflow():
    text = (ENTITY_ROOT / "porters" / "prompts" / "heartbeat.md").read_text(encoding="utf-8")

    assert "ready-" in text
    assert "wip-" in text
    assert "pytest tests -q" in text
    assert "tests/porter_system/" in text


def test_dev_entities_document_branch_naming_policy():
    nutshell_dev_heartbeat = (ENTITY_ROOT / "nutshell_dev" / "prompts" / "heartbeat.md").read_text(encoding="utf-8")
    nutshell_dev_track_sop = (ENTITY_ROOT / "nutshell_dev" / "memory" / "track_sop.md").read_text(encoding="utf-8")
    nutshell_dev_codex_track_sop = (ENTITY_ROOT / "nutshell_dev_codex" / "memory" / "track_sop.md").read_text(encoding="utf-8")
    nutshell_dev_codex_memory = (ENTITY_ROOT / "nutshell_dev_codex" / "memory.md").read_text(encoding="utf-8")

    for text in (
        nutshell_dev_heartbeat,
        nutshell_dev_track_sop,
        nutshell_dev_codex_track_sop,
        nutshell_dev_codex_memory,
    ):
        assert "wip-" in text
        assert "ready-" in text
