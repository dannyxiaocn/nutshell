"""send_to_session built-in tool — session-to-session messaging via FileIPC."""
from __future__ import annotations

import asyncio
import json
import os
import uuid as _uuid_mod
from datetime import datetime
from pathlib import Path

# Allow uuid to be overridden in tests
uuid = _uuid_mod

_DEFAULT_SYSTEM_BASE = Path(__file__).parent.parent.parent.parent / "_sessions"
_POLL_INTERVAL = 0.5


async def send_to_session(
    *,
    session_id: str,
    message: str,
    mode: str = "sync",
    timeout: float = 60.0,
    _system_base: Path | None = None,
) -> str:
    """Send a message to another Nutshell session.

    Args:
        session_id: Target session ID.
        message: Message content to send.
        mode: "sync" (wait for reply) or "async" (fire-and-forget).
        timeout: Max seconds to wait in sync mode.
        _system_base: Override _sessions/ directory (for testing).

    Returns:
        In sync mode: the agent's response text, or an error string.
        In async mode: confirmation string.
    """
    system_base = _system_base if _system_base is not None else _DEFAULT_SYSTEM_BASE
    target_dir = system_base / session_id

    # Self-call guard
    current_sid = os.environ.get("NUTSHELL_SESSION_ID", "")
    if current_sid and current_sid == session_id:
        return f"Error: cannot send to own session ({session_id})."

    # Existence check
    if not (target_dir / "manifest.json").exists():
        return f"Error: session '{session_id}' not found."

    ctx_path = target_dir / "context.jsonl"

    # Write user_input
    msg_id = str(uuid.uuid4())
    _append_jsonl(ctx_path, {
        "type": "user_input",
        "content": message,
        "id": msg_id,
        "ts": datetime.now().isoformat(),
    })

    if mode == "async":
        return f"Message sent to session {session_id}."

    # Sync: poll for matching turn
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        reply = _find_turn(ctx_path, msg_id)
        if reply is not None:
            return reply
        await asyncio.sleep(_POLL_INTERVAL)

    return f"Timeout: no response from session '{session_id}' within {timeout:.0f}s."


def _append_jsonl(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _find_turn(ctx_path: Path, msg_id: str) -> str | None:
    """Scan context.jsonl for a turn with user_input_id == msg_id.

    Returns the last assistant text if found, else None.
    Returns empty string if the turn exists but has no text.
    """
    if not ctx_path.exists():
        return None
    try:
        with ctx_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "turn":
                    continue
                if event.get("user_input_id") != msg_id:
                    continue
                # Found matching turn — extract last assistant text
                for msg in reversed(event.get("messages", [])):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    return block.get("text", "")
                return ""
    except Exception:
        return None
    return None
