from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from nutshell.core.agent import Agent
from nutshell.core.tool import tool
from nutshell.core.types import AgentResult

INSTANCES_DIR = Path("instances")
DEFAULT_HEARTBEAT_INTERVAL = 10.0  # seconds


class Instance:
    """Agent persistent run context.

    Disk layout: instances/<id>/
        kanban.md    — free-form task notes (plain file read/write)
        context.json — IO event log
        files/       — associated files directory

    Typical usage:
        async with Instance(agent, heartbeat=20) as inst:
            result = await inst.chat("hello")

    Or manually:
        inst = Instance(agent, heartbeat=20)
        await inst.start()
        result = await inst.chat("hello")
        await inst.stop()
    """

    def __init__(
        self,
        agent: Agent,
        instance_id: str | None = None,
        base_dir: Path = INSTANCES_DIR,
        heartbeat: float = DEFAULT_HEARTBEAT_INTERVAL,
        on_tick: Callable | None = None,
        on_done: Callable | None = None,
    ) -> None:
        self._agent = agent
        self._instance_id = instance_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._base_dir = base_dir
        self._heartbeat_interval = heartbeat
        self._on_tick = on_tick
        self._on_done = on_done
        self._stop = False
        self._notify_event: asyncio.Event = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None
        self._agent_lock: asyncio.Lock = asyncio.Lock()

        # Create directory structure
        self.instance_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(exist_ok=True)
        if not self.kanban_path.exists():
            self.kanban_path.write_text("", encoding="utf-8")
        if not self._context_path.exists():
            self._context_path.write_text("[]", encoding="utf-8")

        # Inject kanban tools
        kanban_path = self.kanban_path

        @tool(description="Read the current kanban board")
        def read_kanban() -> str:
            content = kanban_path.read_text(encoding="utf-8").strip()
            return content or "(empty)"

        @tool(description="Overwrite the kanban board. Pass empty string to clear all tasks.")
        def write_kanban(content: str) -> str:
            kanban_path.write_text(content, encoding="utf-8")
            return "Kanban updated."

        agent.tools.extend([read_kanban, write_kanban])

    @classmethod
    def resume(
        cls,
        instance_id: str,
        agent: Agent,
        base_dir: Path = INSTANCES_DIR,
        heartbeat: float = DEFAULT_HEARTBEAT_INTERVAL,
        on_tick: Callable | None = None,
        on_done: Callable | None = None,
    ) -> "Instance":
        """Resume from an existing directory without rebuilding files."""
        instance = cls.__new__(cls)
        instance._agent = agent
        instance._instance_id = instance_id
        instance._base_dir = base_dir
        instance._heartbeat_interval = heartbeat
        instance._on_tick = on_tick
        instance._on_done = on_done
        instance._stop = False
        instance._notify_event = asyncio.Event()
        instance._heartbeat_task = None
        instance._agent_lock = asyncio.Lock()

        kanban_path = instance.kanban_path

        @tool(description="Read the current kanban board")
        def read_kanban() -> str:
            content = kanban_path.read_text(encoding="utf-8").strip()
            return content or "(empty)"

        @tool(description="Overwrite the kanban board. Pass empty string to clear all tasks.")
        def write_kanban(content: str) -> str:
            kanban_path.write_text(content, encoding="utf-8")
            return "Kanban updated."

        agent.tools.extend([read_kanban, write_kanban])
        return instance

    # ── Lifecycle ─────────────────────────────────────

    async def start(self) -> "Instance":
        """Start background heartbeat task."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(
                self.start_heartbeat(interval=self._heartbeat_interval)
            )
        return self

    async def stop(self) -> None:
        """Stop background heartbeat task and write final status."""
        if self._heartbeat_task is not None:
            self.stop_heartbeat()
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        self.close()

    def silence(self) -> None:
        """Clear on_tick/on_done callbacks so heartbeat runs silently in background."""
        self._on_tick = None
        self._on_done = None

    async def __aenter__(self) -> "Instance":
        return await self.start()

    async def __aexit__(self, *_) -> None:
        await self.stop()

    # ── Activation ────────────────────────────────────

    async def chat(self, message: str) -> AgentResult:
        """Run agent with user message. Holds agent lock — blocks heartbeat tick."""
        self._append_event({"type": "user", "content": message})
        async with self._agent_lock:
            result = await self._agent.run(message)
        self._append_event({"type": "agent", "content": result.content})
        for tc in result.tool_calls:
            self._append_event({"type": "tool", "name": tc.name, "input": tc.input})
        return result

    async def tick(self) -> AgentResult | None:
        """Single heartbeat: run agent if kanban is non-empty. Holds agent lock — blocks chat."""
        kanban_content = self.kanban_path.read_text(encoding="utf-8").strip()
        if not kanban_content:
            return None
        prompt = (
            f"Check your kanban and continue working.\n\n"
            f"--- Kanban ---\n{kanban_content}\n---\n\n"
            f"When you finish ALL tasks, you MUST call write_kanban(\"\") to clear the board. "
            f"This is the only way to signal completion. Do not just say tasks are done — "
            f"you must actually call write_kanban(\"\")."
        )
        self._append_event({"type": "tick", "kanban": kanban_content})
        async with self._agent_lock:
            result = await self._agent.run(prompt)
        self._append_event({"type": "agent", "content": result.content})
        return result

    # ── Heartbeat (built-in) ──────────────────────────

    async def start_heartbeat(self, interval: float = 900.0) -> None:
        """Start timed heartbeat loop. Reads self._on_tick / self._on_done at call time
        so callbacks can be silenced mid-run via silence().
        """
        self._stop = False
        self._notify_event.clear()

        while not self._stop:
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._notify_event.wait()),
                    timeout=interval,
                )
            except asyncio.TimeoutError:
                pass

            self._notify_event.clear()

            if self._stop:
                break

            result = await self.tick()
            if self._on_tick is not None and result is not None:
                self._on_tick(result)

            if self.is_done():
                if self._on_done is not None:
                    self._on_done()
                break

    async def notify(self) -> None:
        """Immediately wake the heartbeat loop."""
        self._notify_event.set()

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat loop."""
        self._stop = True
        self._notify_event.set()

    # ── Lifecycle ─────────────────────────────────────

    def is_done(self) -> bool:
        """True when kanban is empty."""
        return not self.kanban_path.read_text(encoding="utf-8").strip()

    def close(self, status: str = "done") -> None:
        """Write final status event to context.json. Called automatically by stop()."""
        self._append_event({"type": "status", "value": status})

    # ── Properties ────────────────────────────────────

    @property
    def instance_dir(self) -> Path:
        return self._base_dir / self._instance_id

    @property
    def files_dir(self) -> Path:
        return self.instance_dir / "files"

    @property
    def kanban_path(self) -> Path:
        return self.instance_dir / "kanban.md"

    @property
    def _context_path(self) -> Path:
        return self.instance_dir / "context.json"

    # ── Internal ──────────────────────────────────────

    def _append_event(self, event: dict) -> None:
        event["timestamp"] = datetime.now().isoformat()
        events: list = json.loads(self._context_path.read_text(encoding="utf-8"))
        events.append(event)
        self._context_path.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
