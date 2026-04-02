"""CAP — Cambridge Agent Protocol primitives for supervised multi-agent coordination.

CAP provides a small runtime abstraction layer for system-governed coordination
between sessions. Agent-facing apps such as QJBQ or spawn_session initiate work;
CAP defines the passive protocol primitives the runtime can enforce and audit.

Initial primitive set:
- handshake      — register a peer relationship / protocol participation
- lock           — acquire/release/check named coordination locks
- broadcast      — append a protocol event for all interested participants
- heartbeat-sync — record / inspect the latest heartbeat tick per session

The first concrete protocol implementation is git coordination, exposed via the
GitCoordinator adapter.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from nutshell.runtime.git_coordinator import GitCoordinator

_DEFAULT_SYSTEM_BASE = Path(__file__).parent.parent.parent / "_sessions"

CapPrimitive = Literal["handshake", "lock", "broadcast", "heartbeat-sync"]
LockState = Literal["acquired", "busy", "released", "free"]


class CAP:
    """Small file-backed coordination layer for runtime protocols."""

    def __init__(self, system_base: Path | None = None) -> None:
        self._system_base = system_base or _DEFAULT_SYSTEM_BASE
        self._cap_dir = self._system_base / "cap"
        self._locks_dir = self._cap_dir / "locks"
        self._heartbeats_dir = self._cap_dir / "heartbeats"
        self._cap_dir.mkdir(parents=True, exist_ok=True)
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        self._heartbeats_dir.mkdir(parents=True, exist_ok=True)
        self._handshakes_path = self._cap_dir / "handshakes.json"
        self._broadcast_path = self._cap_dir / "broadcast.jsonl"

    def primitives(self) -> tuple[CapPrimitive, ...]:
        return ("handshake", "lock", "broadcast", "heartbeat-sync")

    def handshake(self, protocol: str, source_session: str, target_session: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        registry = self._load_json(self._handshakes_path, default={})
        key = self._handshake_key(protocol, source_session, target_session)
        entry = {
            "protocol": protocol,
            "source_session": source_session,
            "target_session": target_session,
            "metadata": metadata or {},
            "ts": datetime.now().isoformat(),
        }
        registry[key] = entry
        self._save_json(self._handshakes_path, registry)
        return entry

    def get_handshake(self, protocol: str, source_session: str, target_session: str) -> dict[str, Any] | None:
        registry = self._load_json(self._handshakes_path, default={})
        return registry.get(self._handshake_key(protocol, source_session, target_session))

    def acquire_lock(self, name: str, owner_session: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self._locks_dir / f"{self._safe_name(name)}.json"
        entry = self._load_json(path, default=None)
        now = datetime.now().isoformat()
        if entry and entry.get("owner_session") not in (None, owner_session):
            return {
                "name": name,
                "state": "busy",
                "owner_session": entry.get("owner_session"),
                "metadata": entry.get("metadata", {}),
                "ts": entry.get("ts"),
            }
        new_entry = {
            "name": name,
            "state": "acquired",
            "owner_session": owner_session,
            "metadata": metadata or {},
            "ts": now,
        }
        self._save_json(path, new_entry)
        return new_entry

    def release_lock(self, name: str, owner_session: str) -> dict[str, Any]:
        path = self._locks_dir / f"{self._safe_name(name)}.json"
        entry = self._load_json(path, default=None)
        if not entry:
            return {"name": name, "state": "free", "owner_session": None}
        if entry.get("owner_session") != owner_session:
            return {
                "name": name,
                "state": "busy",
                "owner_session": entry.get("owner_session"),
                "metadata": entry.get("metadata", {}),
                "ts": entry.get("ts"),
            }
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return {"name": name, "state": "released", "owner_session": owner_session}

    def get_lock(self, name: str) -> dict[str, Any]:
        path = self._locks_dir / f"{self._safe_name(name)}.json"
        entry = self._load_json(path, default=None)
        if not entry:
            return {"name": name, "state": "free", "owner_session": None}
        return entry

    def broadcast(self, channel: str, sender_session: str, content: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "channel": channel,
            "sender_session": sender_session,
            "content": content,
            "metadata": metadata or {},
            "ts": datetime.now().isoformat(),
        }
        self._append_jsonl(self._broadcast_path, event)
        return event

    def list_broadcasts(self, channel: str | None = None) -> list[dict[str, Any]]:
        events = self._load_jsonl(self._broadcast_path)
        if channel is None:
            return events
        return [e for e in events if e.get("channel") == channel]

    def sync_heartbeat(self, session_id: str, *, heartbeat_at: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            "session_id": session_id,
            "heartbeat_at": heartbeat_at or datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._save_json(self._heartbeats_dir / f"{self._safe_name(session_id)}.json", entry)
        return entry

    def get_heartbeat(self, session_id: str) -> dict[str, Any] | None:
        return self._load_json(self._heartbeats_dir / f"{self._safe_name(session_id)}.json", default=None)

    def git_protocol(self) -> GitCoordinator:
        """Expose git coordination as the first CAP protocol adapter."""
        return GitCoordinator(system_base=self._system_base)

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(c for c in value if c.isalnum() or c in "-_:") or "default"

    @staticmethod
    def _handshake_key(protocol: str, source_session: str, target_session: str) -> str:
        return f"{protocol}:{source_session}->{target_session}"

    def _save_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def _append_jsonl(self, path: Path, event: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
        return out
