from __future__ import annotations

import argparse
from pathlib import Path

from unit_test._runner import discover_and_run, repo_root_from, run_subunit_go_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nutshell full-system unit tests.")
    parser.add_argument(
        "--include-units",
        action="store_true",
        help="Also run every sub-directory unit_test/go.py runner after the full-system suite.",
    )
    parser.add_argument(
        "--units-only",
        action="store_true",
        help="Skip root full-system tests and run only the sub-directory unit runners.",
    )
    args = parser.parse_args()

    root = repo_root_from(Path(__file__))
    if not args.units_only:
        exit_code = discover_and_run(Path(__file__).resolve().parent, top_level=root)
        if exit_code != 0:
            return exit_code
    if args.include_units or args.units_only:
        return run_subunit_go_files(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

