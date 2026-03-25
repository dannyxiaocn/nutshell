"""Shared session initialization — creates session directory structure from an entity.

Used by:
  - ui/web/sessions.py  (web UI new-session endpoint)
  - nutshell/tool_engine/providers/spawn_session.py  (agent tool)
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from nutshell.runtime.params import ensure_session_params, write_session_params
from nutshell.runtime.status import ensure_session_status, write_session_status

_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_SESSIONS_BASE = _REPO_ROOT / "sessions"
_DEFAULT_SYSTEM_SESSIONS_BASE = _REPO_ROOT / "_sessions"
_DEFAULT_ENTITY_BASE = _REPO_ROOT / "entity"


def _write_if_absent(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")




def _load_entity_params(entity_dir: Path) -> dict:
    """Read the ``params`` mapping from an entity's agent.yaml (if any).

    Returns a dict of param overrides (e.g. persistent, default_task,
    heartbeat_interval) that should be written into the session's params.json.
    """
    yaml_path = entity_dir / "agent.yaml"
    if not yaml_path.exists():
        return {}
    try:
        import yaml
        manifest = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return dict(manifest.get("params") or {})

def init_session(
    session_id: str,
    entity_name: str,
    *,
    sessions_base: Path | None = None,
    system_sessions_base: Path | None = None,
    entity_base: Path | None = None,
    heartbeat: float = 600.0,
    initial_message: str | None = None,
) -> str:
    """Create a new session on disk from an entity, ready for the server to pick up.

    Returns the session_id. Idempotent: only writes files that do not exist yet.

    Args:
        session_id:          The unique session identifier (e.g. '2026-03-25_10-00-00').
        entity_name:         Name of the entity in entity_base/ (e.g. 'agent', 'kimi_agent').
        sessions_base:       Root of agent-visible sessions/ directory.
        system_sessions_base: Root of _sessions/ directory.
        entity_base:         Root of entity/ directory.
        heartbeat:           Heartbeat interval in seconds (default: 600).
        initial_message:     Optional first user message to write to context.jsonl.
    """
    s_base = sessions_base or _DEFAULT_SESSIONS_BASE
    sys_base = system_sessions_base or _DEFAULT_SYSTEM_SESSIONS_BASE
    ent_base = entity_base or _DEFAULT_ENTITY_BASE

    session_dir = s_base / session_id
    system_dir = sys_base / session_id
    core_dir = session_dir / "core"

    # Create directory tree
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "tools").mkdir(exist_ok=True)
    (core_dir / "skills").mkdir(exist_ok=True)
    (session_dir / "docs").mkdir(exist_ok=True)
    (session_dir / "playground").mkdir(exist_ok=True)
    system_dir.mkdir(parents=True, exist_ok=True)

    context_path = system_dir / "context.jsonl"
    events_path = system_dir / "events.jsonl"
    context_path.touch(exist_ok=True)
    events_path.touch(exist_ok=True)

    # Write manifest (always overwritten so entity is current)
    manifest = {
        "session_id": session_id,
        "entity": entity_name,
        "created_at": datetime.now().isoformat(),
    }
    (system_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Load entity and copy files to core/
    entity_dir = ent_base / entity_name
    agent = None
    if entity_dir.exists():
        try:
            from nutshell.llm_engine.loader import AgentLoader
            agent = AgentLoader().load(entity_dir)
        except Exception as e:
            print(f"[session_factory] Warning: failed to load entity '{entity_name}': {e}")

    # Load entity-level param overrides (persistent, default_task, etc.)
    entity_params = _load_entity_params(entity_dir)
    # Entity heartbeat_interval overrides the caller's default
    effective_heartbeat = entity_params.pop("heartbeat_interval", None) or heartbeat

    if agent is not None:
        _write_if_absent(core_dir / "system.md", agent.system_prompt or "")
        _write_if_absent(core_dir / "heartbeat.md", agent.heartbeat_prompt or "")
        _write_if_absent(core_dir / "session.md", agent.session_context_template or "")

        for t in agent.tools:
            tool_json = core_dir / "tools" / f"{t.name}.json"
            if not tool_json.exists():
                schema = {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.schema,
                }
                tool_json.write_text(
                    json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
                )

        for s in agent.skills:
            skill_dir = core_dir / "skills" / s.name
            if not skill_dir.exists():
                if s.location is not None:
                    src_dir = s.location.parent
                    if src_dir.is_dir():
                        shutil.copytree(src_dir, skill_dir, dirs_exist_ok=True)
                    else:
                        skill_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s.location, skill_dir / "SKILL.md")
                else:
                    skill_dir.mkdir(parents=True, exist_ok=True)
                    content = (
                        f"---\nname: {s.name}\ndescription: {s.description}\n---\n\n{s.body}\n"
                    )
                    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        if not (core_dir / "params.json").exists():
            from nutshell.llm_engine.registry import provider_name as pname
            entity_provider = pname(agent._provider) or "anthropic"
            write_session_params(
                session_dir,
                heartbeat_interval=effective_heartbeat,
                model=agent.model,
                provider=entity_provider,
                **entity_params,
            )
        else:
            write_session_params(session_dir, heartbeat_interval=effective_heartbeat, **entity_params)
    else:
        for fname in ("system.md", "heartbeat.md", "session.md"):
            _write_if_absent(core_dir / fname, "")
        if not (core_dir / "params.json").exists():
            ensure_session_params(session_dir, heartbeat_interval=effective_heartbeat, **entity_params)
        else:
            write_session_params(session_dir, heartbeat_interval=effective_heartbeat, **entity_params)

    # Seed memory.md from entity if the entity provides one
    entity_memory = (ent_base / entity_name / "memory.md") if entity_dir.exists() else None
    if entity_memory and entity_memory.exists():
        _write_if_absent(core_dir / "memory.md", entity_memory.read_text(encoding="utf-8"))
    else:
        _write_if_absent(core_dir / "memory.md", "")

    # Seed layered memory from entity memory/ directory
    # Copies .md files from entity/<name>/memory/ → session/core/memory/
    # Only copies files that do not already exist (idempotent).
    entity_memory_dir = ent_base / entity_name / "memory"
    if entity_memory_dir.is_dir():
        session_memory_dir = core_dir / "memory"
        session_memory_dir.mkdir(exist_ok=True)
        for src_file in sorted(entity_memory_dir.glob("*.md")):
            dst_file = session_memory_dir / src_file.name
            if not dst_file.exists():
                shutil.copy2(src_file, dst_file)

    _write_if_absent(core_dir / "tasks.md", "")

    ensure_session_status(system_dir)
    write_session_status(system_dir, heartbeat_interval=effective_heartbeat)

    # Write optional initial message
    if initial_message:
        import uuid
        event = {
            "type": "user_input",
            "content": initial_message,
            "id": str(uuid.uuid4()),
            "ts": datetime.now().isoformat(),
        }
        with context_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return session_id
