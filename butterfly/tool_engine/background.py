"""BackgroundTaskManager — owns the lifecycle of non-blocking tool calls.

One manager per session. Tool calls with `run_in_background=true` are routed
here by the agent loop; the manager:

  1. Spawns a subprocess (currently only supports shell-command-based tools;
     bash is the first opt-in).
  2. Creates a `PanelEntry` under `sessions/<id>/core/panel/<tid>.json`.
  3. Streams stdout/stderr-merged bytes to `_sessions/<id>/tool_results/<tid>.txt`
     as they arrive (non-blocking for the agent).
  4. Fires events on an `asyncio.Queue` for the session daemon:
       - `completed` — process exited (emit once)
       - `stalled`   — 5 min silence (emit once per silent period)
       - `progress`  — polling_interval tick with delta bytes (emit each tick)
       - `killed_by_restart` — server started with orphaned running entries
     The daemon consumes these events and appends user-role notifications to
     `context.jsonl` exactly once (append-once TTL avoidance — see
     `docs/butterfly/tool_engine/design.md` §8).

This module is deliberately tool-agnostic within the shell-command space: any
backgroundable tool whose execution is "run a shell command and stream its
output" can use it. Session-shell-style multi-step or REPL-style tools are not
backgroundable and never reach this manager.
"""
from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from butterfly.session_engine.panel import (
    PanelEntry,
    STATUS_COMPLETED,
    STATUS_KILLED,
    STATUS_KILLED_BY_RESTART,
    STATUS_RUNNING,
    STATUS_STALLED,
    create_pending_tool_entry,
    list_entries,
    load_entry,
    save_entry,
    sweep_killed_by_restart,
)

# 5 minutes of no output → fire stall once
_STALL_SECONDS = 300.0

# Read chunk size for draining stdout
_CHUNK_SIZE = 4096


@dataclass
class BackgroundEvent:
    """An event emitted by the manager for the session daemon to handle."""
    tid: str
    kind: str          # "completed" | "stalled" | "progress" | "killed_by_restart"
    entry: PanelEntry  # Current state snapshot at event time
    delta_text: str = ""  # For "progress" events: new bytes since last delivery


class BackgroundTaskManager:
    """Per-session manager for non-blocking tool calls.

    Args:
        panel_dir: `sessions/<id>/core/panel/` — where panel entry JSON files live.
        tool_results_dir: `_sessions/<id>/tool_results/` — where output files live.
        venv_env_provider: Callable returning an env dict to apply when spawning
            subprocesses (for venv activation). None = inherit the parent env.
    """

    def __init__(
        self,
        panel_dir: Path,
        tool_results_dir: Path,
        venv_env_provider: Callable[[], dict[str, str] | None] | None = None,
    ) -> None:
        self._panel_dir = panel_dir
        self._tool_results_dir = tool_results_dir
        self._venv_env_provider = venv_env_provider
        self._tasks: dict[str, asyncio.Task] = {}
        self._events: asyncio.Queue[BackgroundEvent] = asyncio.Queue()

    @property
    def events(self) -> asyncio.Queue[BackgroundEvent]:
        return self._events

    # ── Public API ────────────────────────────────────────────────────────

    async def spawn(
        self,
        tool_name: str,
        input: dict[str, Any],
        polling_interval: int | None = None,
    ) -> str:
        """Spawn a non-blocking shell command. Returns the tid immediately.

        Only shell-command tools (bash) are supported today; the manager reads
        `input["command"]` + `input.get("workdir")` + `input.get("stdin")`. A
        future extension could delegate to a per-tool spawn helper.
        """
        command = input.get("command")
        if not command:
            raise ValueError("BackgroundTaskManager.spawn: input.command is required")

        entry = create_pending_tool_entry(
            self._panel_dir,
            tool_name=tool_name,
            input=dict(input),  # copy so later mutations don't leak
            polling_interval=polling_interval,
        )
        output_file = self._tool_results_dir / f"{entry.tid}.txt"
        entry.output_file = str(output_file)
        save_entry(self._panel_dir, entry)

        task = asyncio.create_task(
            self._run(entry.tid, command, input.get("workdir"), input.get("stdin"), polling_interval),
            name=f"bgtask_{entry.tid}",
        )
        self._tasks[entry.tid] = task
        return entry.tid

    async def kill(self, tid: str) -> bool:
        """Kill the subprocess for `tid`. Returns True if it was running."""
        entry = load_entry(self._panel_dir, tid)
        if entry is None or entry.is_terminal():
            return False
        pid = entry.pid
        if pid:
            try:
                # Kill the whole process group we created with start_new_session.
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass  # Already gone, or not ours
        # Let the _run loop detect the exit and fire the completion event. We
        # also preemptively mark the panel entry, so UIs show "killed" fast.
        entry.status = STATUS_KILLED
        entry.finished_at = time.time()
        save_entry(self._panel_dir, entry)
        return True

    def sweep_restart(self) -> list[PanelEntry]:
        """Mark all `running` entries as killed_by_restart and emit events.

        Call once at server/daemon init.
        """
        updated = sweep_killed_by_restart(self._panel_dir)
        for entry in updated:
            try:
                self._events.put_nowait(BackgroundEvent(
                    tid=entry.tid, kind="killed_by_restart", entry=entry,
                ))
            except asyncio.QueueFull:
                pass
        return updated

    async def shutdown(self) -> None:
        """Cancel all in-flight tasks (shell processes are left alone — they
        will be reaped or marked killed_by_restart on next startup)."""
        for task in list(self._tasks.values()):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    # ── Internals ─────────────────────────────────────────────────────────

    async def _run(
        self,
        tid: str,
        command: str,
        workdir: str | None,
        stdin: str | None,
        polling_interval: int | None,
    ) -> None:
        """Actual subprocess lifecycle. Streams output, fires events."""
        output_file = self._tool_results_dir / f"{tid}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        env = self._venv_env_provider() if self._venv_env_provider else None

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=workdir,
                env=env,
                start_new_session=True,  # new process group so kill() hits children too
            )
        except Exception as exc:
            # Spawn failure — write one-line error to output file and mark done.
            output_file.write_text(f"[spawn failed: {exc}]", encoding="utf-8")
            self._transition_terminal(tid, STATUS_COMPLETED, exit_code=-1)
            return

        # Stamp pid into the entry.
        entry = load_entry(self._panel_dir, tid)
        if entry is not None:
            entry.pid = proc.pid
            save_entry(self._panel_dir, entry)

        # Feed stdin if given, then close it.
        if stdin is not None and proc.stdin is not None:
            try:
                proc.stdin.write(stdin.encode())
                await proc.stdin.drain()
            finally:
                proc.stdin.close()

        # Drain stdout continuously to the output file; meanwhile run control
        # loop for stall + polling ticks.
        drain_task = asyncio.create_task(
            self._drain_stdout(proc, output_file, tid),
            name=f"bgtask_{tid}_drain",
        )
        control_task = asyncio.create_task(
            self._control_loop(proc, tid, polling_interval),
            name=f"bgtask_{tid}_control",
        )
        try:
            await proc.wait()
        finally:
            # Let drain finish (EOF arrives naturally after exit).
            try:
                await asyncio.wait_for(drain_task, timeout=2.0)
            except asyncio.TimeoutError:
                drain_task.cancel()
            control_task.cancel()
            try:
                await control_task
            except (asyncio.CancelledError, Exception):
                pass

        # Transition entry — unless a concurrent kill() already set killed.
        entry = load_entry(self._panel_dir, tid)
        final_status = (
            STATUS_KILLED if entry is not None and entry.status == STATUS_KILLED
            else STATUS_COMPLETED
        )
        self._transition_terminal(tid, final_status, exit_code=proc.returncode)

    async def _drain_stdout(
        self, proc: asyncio.subprocess.Process, output_file: Path, tid: str
    ) -> None:
        """Stream merged stdout/stderr to `output_file` as it arrives."""
        assert proc.stdout is not None
        with output_file.open("ab") as out:
            while True:
                chunk = await proc.stdout.read(_CHUNK_SIZE)
                if not chunk:
                    return
                out.write(chunk)
                out.flush()
                # Update last_activity_at on the entry so stall watchdog is fair.
                entry = load_entry(self._panel_dir, tid)
                if entry is None:
                    continue
                entry.last_activity_at = time.time()
                try:
                    entry.output_bytes = output_file.stat().st_size
                except OSError:
                    pass
                save_entry(self._panel_dir, entry)

    async def _control_loop(
        self,
        proc: asyncio.subprocess.Process,
        tid: str,
        polling_interval: int | None,
    ) -> None:
        """Run stall watchdog + (optional) polling heartbeat until cancelled."""
        stall_fired = False
        last_progress_tick = time.time()
        try:
            while proc.returncode is None:
                await asyncio.sleep(1.0)
                now = time.time()
                entry = load_entry(self._panel_dir, tid)
                if entry is None:
                    continue
                silent = now - (entry.last_activity_at or entry.started_at or now)

                if not stall_fired and silent >= _STALL_SECONDS:
                    entry.status = STATUS_STALLED
                    save_entry(self._panel_dir, entry)
                    self._events.put_nowait(BackgroundEvent(
                        tid=tid, kind="stalled", entry=entry,
                    ))
                    stall_fired = True

                if polling_interval and (now - last_progress_tick) >= polling_interval:
                    delta = self._read_delta(entry)
                    if delta:
                        self._events.put_nowait(BackgroundEvent(
                            tid=tid, kind="progress", entry=entry, delta_text=delta,
                        ))
                    last_progress_tick = now
        except asyncio.CancelledError:
            return

    def _read_delta(self, entry: PanelEntry) -> str:
        """Read new bytes from entry.output_file since last delivery.
        Updates `last_delivered_bytes` on the entry in place, saves it.
        """
        if not entry.output_file:
            return ""
        output_path = Path(entry.output_file)
        if not output_path.exists():
            return ""
        try:
            with output_path.open("rb") as f:
                f.seek(entry.last_delivered_bytes)
                delta_bytes = f.read()
        except OSError:
            return ""
        if not delta_bytes:
            return ""
        entry.last_delivered_bytes += len(delta_bytes)
        save_entry(self._panel_dir, entry)
        return delta_bytes.decode(errors="replace")

    def _transition_terminal(
        self, tid: str, status: str, *, exit_code: int | None
    ) -> None:
        entry = load_entry(self._panel_dir, tid)
        if entry is None:
            return
        entry.status = status
        entry.exit_code = exit_code
        entry.finished_at = time.time()
        output_path = Path(entry.output_file) if entry.output_file else None
        if output_path and output_path.exists():
            try:
                entry.output_bytes = output_path.stat().st_size
            except OSError:
                pass
        save_entry(self._panel_dir, entry)
        self._events.put_nowait(BackgroundEvent(
            tid=tid, kind="completed", entry=entry,
        ))
