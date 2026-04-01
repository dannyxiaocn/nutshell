"""Dream mechanism — periodic meta-session cleanup and session management.

Dream reviews all sessions belonging to an entity, classifies them,
updates meta memory with tracked session info, and cleans up old sessions.
No LLM calls — purely rule-based for speed.
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SessionClass = Literal[
    "keep_active",
    "keep_tracked",
    "alignment_blocked",
    "archive",
    "delete",
]

# Defaults when agent.yaml has no dream config
_DEFAULT_DREAM_CONFIG = {
    "max_sessions": 50,
    "max_playground_mb": 500,
    "dream_threshold": 30,
    "dream_interval": 21600,  # 6 hours
}


@dataclass
class SessionInfo:
    session_id: str
    entity: str
    status: str
    created_at: str
    last_activity: str  # last modified time of context.jsonl or status.json
    context_bytes: int
    task_summary: str  # first non-empty line of tasks.md, or ''
    classification: SessionClass = "delete"
    playground_mb: float = 0.0


@dataclass
class DreamReport:
    entity: str
    timestamp: str = ""
    sessions_reviewed: int = 0
    kept: list[str] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    freed_mb: float = 0.0
    meta_playground_mb: float = 0.0
    total_sessions_mb: float = 0.0
    warnings: list[str] = field(default_factory=list)


def run_dream(
    entity_name: str,
    *,
    dry_run: bool = False,
    entity_base: Path | None = None,
    s_base: Path | None = None,
    sys_base: Path | None = None,
    force: bool = False,
) -> DreamReport:
    """Run a dream cycle for the given entity.

    Scans all sessions, classifies them, updates meta memory, and
    cleans up archive/delete sessions.

    Args:
        entity_name: Entity to dream for.
        dry_run: If True, classify and report but don't delete anything.
        entity_base: Root of entity/ directory.
        s_base: Root of sessions/ directory.
        sys_base: Root of _sessions/ directory.
        force: Skip dream_interval cooldown check.

    Returns:
        DreamReport with classification results and cleanup stats.
    """
    s_base = s_base or _REPO_ROOT / "sessions"
    sys_base = sys_base or _REPO_ROOT / "_sessions"
    ent_base = entity_base or _REPO_ROOT / "entity"

    now = datetime.now()
    config = _get_dream_config(entity_name, ent_base)

    # Check cooldown (unless forced)
    if not force:
        meta_dir = s_base / f"{entity_name}_meta"
        last_dream_file = meta_dir / "core" / ".last_dream"
        if last_dream_file.exists():
            try:
                last_ts = float(last_dream_file.read_text(encoding="utf-8").strip())
                elapsed = time.time() - last_ts
                if elapsed < config["dream_interval"]:
                    report = DreamReport(entity=entity_name, timestamp=now.isoformat())
                    report.warnings.append(
                        f"Skipped: only {elapsed:.0f}s since last dream "
                        f"(interval={config['dream_interval']}s). Use --force to override."
                    )
                    return report
            except (ValueError, OSError):
                pass

    # Discover sessions for this entity
    sessions = _discover_sessions(entity_name, s_base, sys_base)

    # Classify each session
    for info in sessions:
        info.classification = _classify_session(info, now, force=force)

    report = DreamReport(
        entity=entity_name,
        timestamp=now.isoformat(),
        sessions_reviewed=len(sessions),
    )

    # Process classifications
    freed_mb = 0.0
    for info in sessions:
        if info.classification in ("keep_active", "keep_tracked", "alignment_blocked"):
            report.kept.append(info.session_id)
        elif info.classification == "archive":
            report.archived.append(info.session_id)
            if not dry_run:
                freed_mb += _delete_session(info.session_id, s_base, sys_base, dry_run=False)
        elif info.classification == "delete":
            report.deleted.append(info.session_id)
            if not dry_run:
                freed_mb += _delete_session(info.session_id, s_base, sys_base, dry_run=False)

    report.freed_mb = round(freed_mb, 2)

    # Enforce max_sessions: if still over limit, delete oldest stopped sessions
    if not dry_run:
        remaining = _discover_sessions(entity_name, s_base, sys_base)
        max_sessions = config["max_sessions"]
        if len(remaining) > max_sessions:
            # Sort by created_at ascending, prefer deleting oldest stopped first
            stopped = sorted(
                [s for s in remaining if s.status == "stopped"],
                key=lambda s: s.created_at,
            )
            to_remove = len(remaining) - max_sessions
            for info in stopped[:to_remove]:
                freed_mb += _delete_session(info.session_id, s_base, sys_base, dry_run=False)
                report.deleted.append(info.session_id)
                report.warnings.append(
                    f"Force-deleted {info.session_id} (max_sessions={max_sessions} exceeded)"
                )
            report.freed_mb = round(freed_mb, 2)

    # Check playground size warning
    meta_dir = s_base / f"{entity_name}_meta"
    meta_pg_mb = _dir_size_mb(meta_dir / "playground")
    report.meta_playground_mb = round(meta_pg_mb, 2)
    if meta_pg_mb > config["max_playground_mb"]:
        report.warnings.append(
            f"Meta playground is {meta_pg_mb:.1f}MB "
            f"(limit={config['max_playground_mb']}MB). Consider manual cleanup."
        )

    # Calculate total sessions storage
    total_mb = 0.0
    if s_base.exists():
        for d in s_base.iterdir():
            if d.is_dir() and not d.name.endswith("_meta"):
                total_mb += _dir_size_mb(d)
    report.total_sessions_mb = round(total_mb, 2)

    # Update meta memory (tracked sessions + dream log)
    if not dry_run:
        _update_meta_memory(entity_name, sessions, report, s_base)
        # Record last dream timestamp
        last_dream_file = meta_dir / "core" / ".last_dream"
        last_dream_file.parent.mkdir(parents=True, exist_ok=True)
        last_dream_file.write_text(str(time.time()), encoding="utf-8")

    return report


def _discover_sessions(
    entity_name: str, s_base: Path, sys_base: Path
) -> list[SessionInfo]:
    """Find all sessions belonging to entity_name by reading manifest.json."""
    sessions: list[SessionInfo] = []

    if not sys_base.exists():
        return sessions

    for system_dir in sorted(sys_base.iterdir()):
        if not system_dir.is_dir():
            continue

        session_id = system_dir.name
        # Skip meta sessions
        if session_id.endswith("_meta"):
            continue

        manifest_path = system_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if manifest.get("entity") != entity_name:
            continue

        # Read status
        from nutshell.runtime.status import read_session_status

        status_data = read_session_status(system_dir)
        status = status_data.get("status", "active")

        # Created at
        created_at = manifest.get("created_at", "")

        # Context size (just stat, don't read)
        context_path = system_dir / "context.jsonl"
        context_bytes = 0
        if context_path.exists():
            try:
                context_bytes = context_path.stat().st_size
            except OSError:
                pass

        # Last activity: max mtime of context.jsonl and status.json
        last_activity = created_at
        for check_file in (context_path, system_dir / "status.json"):
            if check_file.exists():
                try:
                    mtime = check_file.stat().st_mtime
                    mtime_iso = datetime.fromtimestamp(mtime).isoformat()
                    if mtime_iso > last_activity:
                        last_activity = mtime_iso
                except OSError:
                    pass

        # Task summary
        session_dir = s_base / session_id
        tasks_path = session_dir / "core" / "tasks.md"
        task_summary = ""
        if tasks_path.exists():
            try:
                lines = tasks_path.read_text(encoding="utf-8").strip().splitlines()
                # First 5 non-empty lines
                non_empty = [ln.strip() for ln in lines if ln.strip()][:5]
                task_summary = "; ".join(non_empty)
            except OSError:
                pass

        # Playground size
        playground_mb = _dir_size_mb(session_dir / "playground") if session_dir.exists() else 0.0

        sessions.append(
            SessionInfo(
                session_id=session_id,
                entity=entity_name,
                status=status,
                created_at=created_at,
                last_activity=last_activity,
                context_bytes=context_bytes,
                task_summary=task_summary,
                playground_mb=round(playground_mb, 2),
            )
        )

    return sessions


def _classify_session(
    info: SessionInfo, now: datetime, *, force: bool = False
) -> SessionClass:
    """Classify a session based on priority rules.

    Priority:
    1. keep_active: running, or idle with recent activity (< 2h)
    2. keep_tracked: tasks.md non-empty
    3. alignment_blocked: status == alignment_blocked
    4. archive: stopped with context, created < 48h ago
    5. delete: everything else
    """
    from nutshell.runtime.status import pid_alive

    # 1. Running sessions are always kept active
    if info.status == "active":
        # Check if recently active (within 2 hours)
        try:
            last = datetime.fromisoformat(info.last_activity)
            if (now - last) < timedelta(hours=2):
                return "keep_active"
        except (ValueError, TypeError):
            pass
        # Active but not recent — still keep if has tasks
        if info.task_summary:
            return "keep_tracked"
        return "keep_active"

    # 3. Alignment blocked
    if info.status == "alignment_blocked":
        return "alignment_blocked"

    # 2. Has tasks → tracked (regardless of status)
    if info.task_summary:
        return "keep_tracked"

    # For stopped sessions:
    if info.status == "stopped":
        # 4. Archive: has context and was created recently (< 48h)
        if info.context_bytes > 0:
            try:
                created = datetime.fromisoformat(info.created_at)
                age = now - created
                if age < timedelta(hours=48):
                    return "archive"
            except (ValueError, TypeError):
                pass
            # Older than 48h with context → also archive
            return "archive"

        # 5. No context → delete
        return "delete"

    # Anything else → delete
    return "delete"


def _get_dream_config(entity_name: str, entity_base: Path) -> dict:
    """Read dream-related config from agent.yaml, with defaults."""
    config = dict(_DEFAULT_DREAM_CONFIG)

    yaml_path = entity_base / entity_name / "agent.yaml"
    if not yaml_path.exists():
        return config

    try:
        import yaml

        manifest = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return config

    # Dream config can be at top level or under a 'dream' key
    dream_section = manifest.get("dream", {})
    if isinstance(dream_section, dict):
        for key in _DEFAULT_DREAM_CONFIG:
            if key in dream_section:
                config[key] = dream_section[key]

    # Also check top-level keys
    for key in _DEFAULT_DREAM_CONFIG:
        if key in manifest and key not in (dream_section or {}):
            config[key] = manifest[key]

    return config


def _update_meta_memory(
    entity_name: str,
    sessions: list[SessionInfo],
    report: DreamReport,
    s_base: Path,
) -> None:
    """Write dream_sessions.md and append to dream_log.md in meta memory."""
    meta_dir = s_base / f"{entity_name}_meta"
    memory_dir = meta_dir / "core" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # dream_sessions.md — overwrite each time
    tracked_lines = [f"# Tracked Sessions — {entity_name}", ""]

    active_tracked = [
        s for s in sessions
        if s.classification in ("keep_active", "keep_tracked", "alignment_blocked")
    ]
    archived = [s for s in sessions if s.classification == "archive"]

    if active_tracked:
        tracked_lines.append("## Active / Tracked")
        for s in active_tracked:
            status_label = s.status
            if s.classification == "alignment_blocked":
                status_label = "alignment_blocked"
            line = f"- `{s.session_id}` [{status_label}]"
            if s.task_summary:
                line += f"\n  Tasks: {s.task_summary}"
            line += f"\n  Path: sessions/{s.session_id}"
            tracked_lines.append(line)
        tracked_lines.append("")

    if archived:
        tracked_lines.append("## Recent Archive")
        for s in archived:
            date_str = s.created_at[:10] if s.created_at else "unknown"
            summary = s.task_summary or "(no tasks)"
            tracked_lines.append(f"- `{s.session_id}` ({date_str}): {summary}")
        tracked_lines.append("")

    (memory_dir / "dream_sessions.md").write_text(
        "\n".join(tracked_lines), encoding="utf-8"
    )

    # dream_log.md — append
    log_path = memory_dir / "dream_log.md"
    log_lines = []
    if log_path.exists():
        log_lines.append(log_path.read_text(encoding="utf-8").rstrip())
        log_lines.append("")

    log_lines.append(f"## Dream {report.timestamp}")
    log_lines.append(
        f"- Reviewed: {report.sessions_reviewed} sessions, "
        f"Kept: {len(report.kept)}, "
        f"Archived: {len(report.archived)}, "
        f"Deleted: {len(report.deleted)}"
    )
    log_lines.append(f"- Freed: {report.freed_mb} MB")
    log_lines.append(
        f"- Storage: {entity_name}_meta playground = {report.meta_playground_mb} MB, "
        f"all sessions = {report.total_sessions_mb} MB"
    )
    if report.warnings:
        for w in report.warnings:
            log_lines.append(f"- ⚠️ {w}")
    log_lines.append("")

    log_path.write_text("\n".join(log_lines), encoding="utf-8")


def _delete_session(
    session_id: str,
    s_base: Path,
    sys_base: Path,
    *,
    dry_run: bool = False,
) -> float:
    """Delete a session's directories. Returns MB freed.

    Deletes both sessions/<id>/ and _sessions/<id>/.
    Safety: re-checks that the session is truly stopped before deleting.
    """
    from nutshell.runtime.status import read_session_status, pid_alive

    system_dir = sys_base / session_id
    session_dir = s_base / session_id

    # Safety check: don't delete running sessions
    if system_dir.exists():
        status_data = read_session_status(system_dir)
        if status_data.get("status") == "active" or pid_alive(status_data.get("pid")):
            return 0.0

    if dry_run:
        return _dir_size_mb(session_dir) + _dir_size_mb(system_dir)

    freed = 0.0
    if session_dir.exists():
        freed += _dir_size_mb(session_dir)
        shutil.rmtree(session_dir, ignore_errors=True)
    if system_dir.exists():
        freed += _dir_size_mb(system_dir)
        shutil.rmtree(system_dir, ignore_errors=True)

    return freed


def _dir_size_mb(path: Path) -> float:
    """Calculate directory size in MB. Returns 0.0 if path doesn't exist."""
    if not path.exists():
        return 0.0
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total / (1024 * 1024)


def should_dream(
    entity_name: str,
    *,
    s_base: Path | None = None,
    sys_base: Path | None = None,
    entity_base: Path | None = None,
) -> bool:
    """Check if a dream should be triggered for this entity.

    Returns True if:
    1. Session count exceeds dream_threshold
    2. Enough time has passed since last dream (dream_interval)
    """
    s_base = s_base or _REPO_ROOT / "sessions"
    sys_base = sys_base or _REPO_ROOT / "_sessions"
    ent_base = entity_base or _REPO_ROOT / "entity"

    config = _get_dream_config(entity_name, ent_base)

    # Count sessions for this entity
    session_count = len(_discover_sessions(entity_name, s_base, sys_base))
    if session_count < config["dream_threshold"]:
        return False

    # Check cooldown
    meta_dir = s_base / f"{entity_name}_meta"
    last_dream_file = meta_dir / "core" / ".last_dream"
    if last_dream_file.exists():
        try:
            last_ts = float(last_dream_file.read_text(encoding="utf-8").strip())
            elapsed = time.time() - last_ts
            if elapsed < config["dream_interval"]:
                return False
        except (ValueError, OSError):
            pass

    return True


def dream_all(
    *,
    dry_run: bool = False,
    entity_base: Path | None = None,
    s_base: Path | None = None,
    sys_base: Path | None = None,
    force: bool = False,
) -> list[DreamReport]:
    """Run dream for all entities that have sessions."""
    s_base = s_base or _REPO_ROOT / "sessions"
    sys_base = sys_base or _REPO_ROOT / "_sessions"
    ent_base = entity_base or _REPO_ROOT / "entity"

    # Discover all entities from manifest files
    entities: set[str] = set()
    if sys_base.exists():
        for system_dir in sys_base.iterdir():
            if not system_dir.is_dir():
                continue
            manifest_path = system_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                entity = manifest.get("entity", "")
                if entity:
                    entities.add(entity)
            except (json.JSONDecodeError, OSError):
                continue

    reports = []
    for entity_name in sorted(entities):
        report = run_dream(
            entity_name,
            dry_run=dry_run,
            entity_base=ent_base,
            s_base=s_base,
            sys_base=sys_base,
            force=force,
        )
        reports.append(report)
    return reports
