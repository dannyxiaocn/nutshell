"""QjbQ CLI — launch the notification relay server.

Usage:
    qjbq-server                     # default: 0.0.0.0:8081
    qjbq-server --port 9090
    qjbq-server --host 127.0.0.1 --port 8081
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="QjbQ — notification relay server for nutshell agents",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8081,
        help="Bind port (default: 8081)",
    )
    parser.add_argument(
        "--sessions-dir",
        default=None,
        metavar="DIR",
        help="Override sessions directory (default: auto-detect)",
    )
    args = parser.parse_args()

    # Set env before importing server (which reads it at module level)
    if args.sessions_dir:
        import os
        os.environ["QJBQ_SESSIONS_DIR"] = args.sessions_dir

    import uvicorn
    uvicorn.run(
        "qjbq.server:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
