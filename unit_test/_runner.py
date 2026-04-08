from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


def repo_root_from(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError(f"Could not locate repository root from {start}")


def discover_and_run(start_dir: Path, *, top_level: Path | None = None) -> int:
    root = top_level or repo_root_from(start_dir)
    loader = unittest.defaultTestLoader
    try:
        suite = loader.discover(
            start_dir=str(start_dir),
            pattern="test_*.py",
            top_level_dir=str(root),
        )
    except ImportError:
        suite = loader.discover(
            start_dir=str(start_dir),
            pattern="test_*.py",
            top_level_dir=str(start_dir),
        )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def iter_subunit_go_files(root: Path) -> list[Path]:
    go_files: list[Path] = []
    for path in sorted(root.rglob("unit_test/go.py")):
        if path.parent == root / "unit_test":
            continue
        go_files.append(path)
    return go_files


def run_subunit_go_files(root: Path) -> int:
    for go_path in iter_subunit_go_files(root):
        print(f"\n==> {go_path.relative_to(root)}")
        completed = subprocess.run([sys.executable, str(go_path)], cwd=root)
        if completed.returncode != 0:
            return completed.returncode
    return 0
