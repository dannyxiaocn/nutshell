"""Review pending entity update requests for the unified `nutshell review` CLI."""
from __future__ import annotations

import sys
from pathlib import Path


def _show_record(record, idx: int, total: int) -> None:
    bar = "─" * 60
    print(f"\n{bar}")
    print(f"  Update {idx}/{total}  [id: {record.id}]")
    print(bar)
    print(f"  Session : {record.session_id}")
    print(f"  Time    : {record.ts}")
    print(f"  File    : {record.file_path}")
    print(f"\n  Reason  : {record.reason}")
    print(f"\n  Content preview ({min(len(record.content), 500)} / {len(record.content)} chars):")
    print("  " + "\n  ".join(record.content[:500].splitlines()))
    if len(record.content) > 500:
        print("  ... (truncated)")
    print(bar)


def review_updates(*, list_only: bool = False, updates_dir: Path | None = None, repo_root: Path | None = None) -> int:
    from nutshell.runtime.env import load_dotenv
    from nutshell.runtime.entity_updates import apply_update, list_pending_updates, reject_update

    load_dotenv()
    pending = list_pending_updates(updates_dir)

    if not pending:
        print("No pending entity update requests.")
        return 0

    print(f"\n{len(pending)} pending update request(s).")

    if list_only:
        for i, record in enumerate(pending, 1):
            print(f"\n  {i}. [{record.ts}] {record.file_path}  (session: {record.session_id})")
            print(f"     Reason: {record.reason[:80]}")
        return 0

    applied = 0
    rejected = 0

    for i, record in enumerate(pending, 1):
        _show_record(record, i, len(pending))
        while True:
            try:
                choice = input("\n  [a]pply / [r]eject / [s]kip / [q]uit: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return 0
            if choice in ("a", "apply"):
                try:
                    apply_update(record.id, updates_base=updates_dir, entity_base=repo_root)
                    print(f"  ✓ Applied — {record.file_path} updated.")
                    applied += 1
                except Exception as exc:
                    print(f"  ✗ Error applying: {exc}", file=sys.stderr)
                break
            if choice in ("r", "reject"):
                try:
                    reject_update(record.id, updates_base=updates_dir)
                    print("  ✗ Rejected.")
                    rejected += 1
                except Exception as exc:
                    print(f"  ✗ Error rejecting: {exc}", file=sys.stderr)
                break
            if choice in ("s", "skip"):
                print("  Skipped.")
                break
            if choice in ("q", "quit"):
                print(f"\nDone. Applied: {applied}, Rejected: {rejected}, Remaining: {len(pending) - i}")
                return 0
            print("  Please enter 'a', 'r', 's', or 'q'.")

    print(f"\nDone. Applied: {applied}, Rejected: {rejected}.")
    return 0


__all__ = ["review_updates"]
