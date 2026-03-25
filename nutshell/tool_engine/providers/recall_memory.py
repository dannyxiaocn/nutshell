"""recall_memory — built-in tool for selective memory retrieval.

Searches the session's memory.md and memory/*.md files for content matching
a query. Returns only the matching lines/paragraphs, avoiding the need to
load all memory into the system prompt.

Best used when memory grows large — call recall_memory(query) to find
relevant facts on demand rather than relying on system-prompt injection.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_DEFAULT_SESSIONS_BASE = _REPO_ROOT / "sessions"
_CONTEXT_LINES = 1  # lines of context around each match


def _search_text(text: str, query: str) -> list[str]:
    """Return non-empty lines that contain the query (case-insensitive)."""
    q_lower = query.lower()
    lines = text.splitlines()
    results: list[str] = []
    for i, line in enumerate(lines):
        if q_lower in line.lower():
            # Add surrounding context
            start = max(0, i - _CONTEXT_LINES)
            end = min(len(lines), i + _CONTEXT_LINES + 1)
            chunk = "\n".join(lines[start:end]).strip()
            if chunk and chunk not in results:
                results.append(chunk)
    return results


async def recall_memory(
    *,
    query: str,
    _sessions_base: Path | None = None,
) -> str:
    """Search session memory for content matching query.

    Searches memory.md and all memory/*.md files. Returns matching
    lines with context. Use when you need to check if a specific fact
    was recorded, without loading all memory into context.

    Args:
        query: Search term (case-insensitive substring match).
    """
    session_id = os.environ.get("NUTSHELL_SESSION_ID", "")
    if not session_id:
        return "Error: no active session (NUTSHELL_SESSION_ID not set)."

    sessions_base = _sessions_base or _DEFAULT_SESSIONS_BASE
    core_dir = sessions_base / session_id / "core"

    if not core_dir.exists():
        return f"Error: session directory not found: {core_dir}"

    hits: list[str] = []

    # Search memory.md
    memory_md = core_dir / "memory.md"
    if memory_md.exists():
        text = memory_md.read_text(encoding="utf-8")
        matches = _search_text(text, query)
        for m in matches:
            hits.append(f"[memory.md]\n{m}")

    # Search memory/*.md
    memory_dir = core_dir / "memory"
    if memory_dir.is_dir():
        for md_file in sorted(memory_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            matches = _search_text(text, query)
            for m in matches:
                hits.append(f"[memory/{md_file.name}]\n{m}")

    if not hits:
        return f"No memory entries found matching '{query}'."

    header = f"Memory matches for '{query}' ({len(hits)} result(s)):\n\n"
    return header + "\n\n---\n\n".join(hits)
