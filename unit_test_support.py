from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def run_unittest_dir(unit_dir: Path, *, verbosity: int = 2) -> int:
    unit_dir = Path(unit_dir).resolve()
    try:
        suite = unittest.defaultTestLoader.discover(
            start_dir=str(unit_dir),
            pattern="test_*.py",
            top_level_dir=str(REPO_ROOT),
        )
    except ImportError:
        suite = unittest.defaultTestLoader.discover(
            start_dir=str(unit_dir),
            pattern="test_*.py",
            top_level_dir=str(unit_dir),
        )
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


def iter_unit_dirs() -> list[Path]:
    roots = [
        REPO_ROOT / "cli_app",
        REPO_ROOT / "entity",
        REPO_ROOT / "nutshell",
        REPO_ROOT / "ui",
    ]
    unit_dirs: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("unit_test")):
            if "__pycache__" in path.parts:
                continue
            unit_dirs.append(path)
    return unit_dirs


def run_full_system(*, include_unit_dirs: bool = False, verbosity: int = 2) -> int:
    status = run_unittest_dir(REPO_ROOT / "unit_test", verbosity=verbosity)
    if status != 0 or not include_unit_dirs:
        return status

    for unit_dir in iter_unit_dirs():
        rel = unit_dir.relative_to(REPO_ROOT)
        print(f"\n==> {rel}")
        sub_status = run_unittest_dir(unit_dir, verbosity=verbosity)
        if sub_status != 0:
            status = sub_status
    return status
