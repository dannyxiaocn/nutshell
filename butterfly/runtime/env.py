"""Shared environment setup utilities for Butterfly CLIs."""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(repo_root: Path | None = None) -> None:
    """Load .env from cwd or repo root into os.environ (best-effort, no deps).

    Searches in order:
      1. Current working directory / .env
      2. repo_root / .env  (if provided)
      3. The directory three levels above this file (repo root heuristic)

    Only sets keys that are NOT already set in the environment.
    """
    candidates: list[Path] = [Path.cwd() / ".env"]
    if repo_root is not None:
        candidates.append(repo_root / ".env")
    # Heuristic: this file is butterfly/runtime/env.py → parent.parent.parent is repo root
    candidates.append(Path(__file__).parent.parent.parent / ".env")

    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        break  # stop after first .env found
