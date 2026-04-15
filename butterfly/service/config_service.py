from __future__ import annotations

from pathlib import Path

import yaml

from butterfly.session_engine.session_config import (
    DEFAULT_CONFIG,
    config_path,
    read_config,
    write_config,
)
from .sessions_service import _validate_session_id, is_meta_session

# Whitelist of keys update_config_yaml / update_config will persist. Anything
# else is silently dropped to prevent schema pollution through the network-
# reachable PUT endpoints. DEFAULT_CONFIG is the sole source of truth.
_ALLOWED_KEYS = frozenset(DEFAULT_CONFIG.keys())


def get_config(session_id: str, sessions_dir: Path, system_sessions_dir: Path) -> dict:
    _validate_session_id(session_id)
    session_dir = sessions_dir / session_id
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists() or not session_dir.exists():
        raise FileNotFoundError(session_id)
    cfg = read_config(session_dir)
    return {**cfg, 'is_meta_session': is_meta_session(session_id)}


def update_config(session_id: str, sessions_dir: Path, system_sessions_dir: Path, params: dict) -> dict:
    _validate_session_id(session_id)
    from butterfly.session_engine.task_cards import ensure_card, load_card, save_card
    session_dir = sessions_dir / session_id
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists() or not session_dir.exists():
        raise FileNotFoundError(session_id)
    # Whitelist the incoming keys against DEFAULT_CONFIG. The PUT endpoints are
    # network-reachable; without this, a client could persist arbitrary keys
    # into the YAML file which then round-trip forever via read_config()'s
    # "{**DEFAULT_CONFIG, **raw}" merge. Not a security issue per-se, but it
    # silently corrupts the schema.
    params = {k: v for k, v in dict(params).items() if k in _ALLOWED_KEYS}

    # Sync duty config field with task card
    duty = params.get('duty')
    if isinstance(duty, dict) and duty.get('interval'):
        tasks_dir = session_dir / 'core' / 'tasks'
        existing = load_card(tasks_dir, 'duty')
        if existing is not None:
            existing.interval = float(duty['interval'])
            existing.description = duty.get('description', existing.description)
            save_card(tasks_dir, existing)
        else:
            ensure_card(tasks_dir, name='duty', interval=float(duty['interval']), description=duty.get('description', ''))

    write_config(session_dir, **params)
    saved = read_config(session_dir)
    return {**saved, 'is_meta_session': is_meta_session(session_id)}


def get_config_yaml(session_id: str, sessions_dir: Path, system_sessions_dir: Path) -> str:
    """Return the raw YAML text for the session's config.yaml.

    If config.yaml doesn't yet exist on disk, return a YAML dump of the
    in-memory defaults (via ``read_config``) so the editor still has
    something sensible to show.
    """
    _validate_session_id(session_id)
    session_dir = sessions_dir / session_id
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists() or not session_dir.exists():
        raise FileNotFoundError(session_id)
    path = config_path(session_dir)
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Fall back to rendered defaults so the UI isn't blank on a never-written session.
    # Leading comment flags this as synthetic so the editor doesn't overwrite it silently.
    cfg = read_config(session_dir)
    cfg.pop('is_meta_session', None)
    dumped = yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return (
        "# Auto-populated defaults — config.yaml did not exist on disk.\n"
        "# Saving from this editor creates the file with the values below.\n"
        + dumped
    )


def update_config_yaml(session_id: str, sessions_dir: Path, system_sessions_dir: Path, yaml_text: str) -> dict:
    """Replace config.yaml with the provided YAML text, then return the parsed dict.

    Raises ValueError if YAML is malformed or doesn't parse to a mapping.
    """
    _validate_session_id(session_id)
    session_dir = sessions_dir / session_id
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists() or not session_dir.exists():
        raise FileNotFoundError(session_id)
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Config YAML must be a mapping")
    parsed.pop('is_meta_session', None)
    # Whitelist-filter here too so we can surface a precise error if the
    # caller sent unknown keys (update_config silently drops them; for the
    # YAML editor we just drop as well — the re-read cycle shows the
    # effective persisted config so the user sees what landed).
    parsed = {k: v for k, v in parsed.items() if k in _ALLOWED_KEYS}
    # Route through update_config so duty-card sync still runs.
    return update_config(session_id, sessions_dir, system_sessions_dir, parsed)
