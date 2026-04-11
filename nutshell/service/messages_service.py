from __future__ import annotations

from pathlib import Path

from .sessions_service import _validate_session_id


def send_message(session_id: str, content: str, system_sessions_dir: Path) -> str:
    _validate_session_id(session_id)
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists():
        raise FileNotFoundError(session_id)
    from nutshell.runtime.bridge import BridgeSession
    return BridgeSession(system_dir).send_message(content)


def interrupt_session(session_id: str, system_sessions_dir: Path) -> None:
    _validate_session_id(session_id)
    system_dir = system_sessions_dir / session_id
    if not system_dir.exists():
        raise FileNotFoundError(session_id)
    from nutshell.runtime.bridge import BridgeSession
    BridgeSession(system_dir).send_interrupt()
