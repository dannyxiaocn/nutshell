"""Nutshell server — backend system.

Watches a _sessions/ directory and runs each discovered session as an
asyncio task. The server itself holds no hard-coded sessions; all sessions
are created by the chat UI writing a manifest.json.

Usage:
    python -m nutshell.runtime.server
    python -m nutshell.runtime.server --sessions-dir ~/my-sessions
    nutshell-server
    nutshell-server --with-qjbq          # also start qjbq-server
"""
import argparse
import asyncio
import signal
import subprocess
import sys
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"
_SYSTEM_SESSIONS_DIR = Path(__file__).parent.parent.parent / "_sessions"


async def _run(sessions_dir: Path, system_sessions_dir: Path) -> None:
    from nutshell.runtime.watcher import SessionWatcher

    watcher = SessionWatcher(sessions_dir, system_sessions_dir)
    stop_event = asyncio.Event()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    print(f"nutshell server started. sessions dir: {sessions_dir.absolute()}")
    await watcher.run(stop_event)
    print("nutshell server stopped.")


def main() -> None:
    from nutshell.runtime.env import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Nutshell server — backend system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sessions-dir",
        default=str(SESSIONS_DIR),
        metavar="DIR",
        help=f"Directory for agent-visible session files (default: {SESSIONS_DIR})",
    )
    parser.add_argument(
        "--system-sessions-dir",
        default=str(_SYSTEM_SESSIONS_DIR),
        metavar="DIR",
        help=f"Directory for system session internals (default: {_SYSTEM_SESSIONS_DIR})",
    )
    parser.add_argument(
        "--with-qjbq",
        action="store_true",
        default=False,
        help="Also start qjbq-server (notification relay) as a background process",
    )
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    system_sessions_dir = Path(args.system_sessions_dir)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    system_sessions_dir.mkdir(parents=True, exist_ok=True)

    # ── Optional: start qjbq-server alongside ────────────────────────
    qjbq_proc = None
    if args.with_qjbq:
        try:
            qjbq_proc = subprocess.Popen(
                [sys.executable, "-m", "qjbq.cli",
                 "--sessions-dir", str(sessions_dir)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            print(f"qjbq-server started (pid {qjbq_proc.pid})")
        except Exception as exc:
            print(f"Warning: failed to start qjbq-server: {exc}")

    try:
        asyncio.run(_run(sessions_dir, system_sessions_dir))
    finally:
        if qjbq_proc is not None:
            qjbq_proc.terminate()
            qjbq_proc.wait(timeout=5)
            print("qjbq-server stopped.")


if __name__ == "__main__":
    main()
