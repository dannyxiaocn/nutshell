import json
from pathlib import Path

DEFAULT_PARAMS: dict = {
    "heartbeat_interval": 600.0,
    "model": None,      # None → use agent.yaml default
    "provider": None,   # None → use Anthropic
}


def params_path(session_dir: Path) -> Path:
    return session_dir / "params.json"


def read_session_params(session_dir: Path) -> dict:
    p = params_path(session_dir)
    if not p.exists():
        return dict(DEFAULT_PARAMS)
    return {**DEFAULT_PARAMS, **json.loads(p.read_text(encoding="utf-8"))}


def write_session_params(session_dir: Path, **updates) -> None:
    current = read_session_params(session_dir)
    current.update(updates)
    params_path(session_dir).write_text(
        json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def ensure_session_params(session_dir: Path, **defaults) -> None:
    """Create params.json if absent. Migrates heartbeat_interval from status.json."""
    p = params_path(session_dir)
    if p.exists():
        return
    # Backward compat: migrate heartbeat_interval from old status.json (check both locations)
    for _spath in [session_dir / "_system_log" / "status.json", session_dir / "status.json"]:
        if _spath.exists():
            try:
                st = json.loads(_spath.read_text(encoding="utf-8"))
                if hi := st.get("heartbeat_interval"):
                    defaults.setdefault("heartbeat_interval", hi)
            except Exception:
                pass
            break
    p.write_text(
        json.dumps({**DEFAULT_PARAMS, **defaults}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
