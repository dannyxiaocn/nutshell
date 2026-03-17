import json
from pathlib import Path

DEFAULT_PARAMS: dict = {
    "heartbeat_interval": 600.0,
    "model": None,          # None → use agent.yaml default
    "provider": None,       # None → use Anthropic
    "tool_providers": {"web_search": "brave"},  # web_search: "brave" | "tavily"
}


def params_path(session_dir: Path) -> Path:
    return session_dir / "core" / "params.json"


def read_session_params(session_dir: Path) -> dict:
    p = params_path(session_dir)
    if not p.exists():
        return dict(DEFAULT_PARAMS)
    return {**DEFAULT_PARAMS, **json.loads(p.read_text(encoding="utf-8"))}


def write_session_params(session_dir: Path, **updates) -> None:
    current = read_session_params(session_dir)
    current.update(updates)
    p = params_path(session_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def ensure_session_params(session_dir: Path, **defaults) -> None:
    """Create core/params.json if absent."""
    p = params_path(session_dir)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({**DEFAULT_PARAMS, **defaults}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
