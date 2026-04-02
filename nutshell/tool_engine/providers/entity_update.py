"""Entity update tools for review-gated entity file changes."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

_UPDATES_DIR_NAME = "_entity_updates"
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


async def propose_entity_update(
    *,
    file_path: str,
    content: str,
    reason: str,
    _entity_base: Path | None = None,
    _updates_base: Path | None = None,
) -> str:
    """Submit a request to update an entity file. Requires human approval."""
    entity_base = _entity_base or (_REPO_ROOT / "entity")
    updates_base = _updates_base or (_REPO_ROOT / _UPDATES_DIR_NAME)

    path = Path(file_path)
    if path.is_absolute():
        return f"Error: file_path must be relative, got absolute path: {file_path!r}"

    try:
        target = (entity_base / path).resolve()
        entity_base_resolved = entity_base.resolve()
        target.relative_to(entity_base_resolved)
    except ValueError:
        return (
            f"Error: invalid file_path {file_path!r} — must be within entity/ directory. "
            f"Example: 'entity/agent/prompts/system.md'"
        )
    except Exception as exc:
        return f"Error: {exc}"

    session_id = os.environ.get("NUTSHELL_SESSION_ID", "unknown")
    record = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now().isoformat(),
        "session_id": session_id,
        "file_path": str(path),
        "content": content,
        "reason": reason,
        "status": "pending",
    }

    updates_base.mkdir(parents=True, exist_ok=True)
    out_path = updates_base / f"{record['id']}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    return (
        f"Update request submitted (id: {record['id']}).\n"
        f"File: {file_path}\n"
        f"Awaiting human review via `nutshell-review-updates`."
    )


def _current_entity_name() -> str | None:
    entity = os.environ.get("NUTSHELL_ENTITY")
    if entity:
        return entity

    session_id = os.environ.get("NUTSHELL_SESSION_ID")
    if not session_id:
        return None

    manifest_path = _REPO_ROOT / "_sessions" / session_id / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    entity = manifest.get("entity")
    return str(entity) if entity else None


def _parent_entity_for_current_session(entity_base: Path) -> str | None:
    entity_name = _current_entity_name()
    if not entity_name:
        return None

    from nutshell.core.loader import AgentConfig

    entity_dir = entity_base / entity_name
    if not entity_dir.exists():
        return None
    try:
        config = AgentConfig.from_path(entity_dir)
    except Exception:
        return None
    return config.extends


async def propose_parent_update(
    *,
    file_path: str,
    content: str,
    reason: str,
    _entity_base: Path | None = None,
    _updates_base: Path | None = None,
) -> str:
    """Submit a request to update a parent entity file. Requires human approval."""
    entity_base = _entity_base or (_REPO_ROOT / "entity")
    updates_base = _updates_base or (_REPO_ROOT / _UPDATES_DIR_NAME)

    parent_name = _parent_entity_for_current_session(entity_base)
    if not parent_name:
        return "Error: current entity has no parent entity (extends is not set or parent could not be resolved)."

    parent_dir = entity_base / parent_name
    if not parent_dir.exists():
        return f"Error: parent entity {parent_name!r} does not exist."

    path = Path(file_path)
    if path.is_absolute():
        return f"Error: file_path must be relative, got absolute path: {file_path!r}"

    repo_relative = Path("entity") / parent_name / path
    try:
        target = (entity_base.parent / repo_relative).resolve()
        target.relative_to(parent_dir.resolve())
    except ValueError:
        return (
            f"Error: invalid file_path {file_path!r} — must resolve within entity/{parent_name}/. "
            f"Example: 'prompts/system.md'"
        )
    except Exception as exc:
        return f"Error: {exc}"

    session_id = os.environ.get("NUTSHELL_SESSION_ID", "unknown")
    record = {
        "id": str(uuid.uuid4()),
        "ts": datetime.now().isoformat(),
        "session_id": session_id,
        "target": "parent",
        "parent_entity": parent_name,
        "file_path": repo_relative.as_posix(),
        "content": content,
        "reason": reason,
        "status": "pending",
    }

    updates_base.mkdir(parents=True, exist_ok=True)
    out_path = updates_base / f"{record['id']}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    return (
        f"Parent update request submitted (id: {record['id']}).\n"
        f"Target: {parent_name}\n"
        f"File: {record['file_path']}\n"
        f"Awaiting human review via `nutshell-review-updates`."
    )
