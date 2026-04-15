"""Grep tool — regex search over file contents.

Prefers ripgrep (`rg`) on PATH; falls back to a pure-Python walker.
"""
from __future__ import annotations

import asyncio
import fnmatch
import re
import shutil
from pathlib import Path
from typing import Any

from butterfly.tool_engine.executor.base import BaseExecutor

_MAX_OUTPUT = 30_000
_TRUNCATE_MARKER = "\n[truncated]"


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + _TRUNCATE_MARKER
    return text


class GrepExecutor(BaseExecutor):
    """Executor for the built-in grep tool."""

    def __init__(self, workdir: str | None = None) -> None:
        self._workdir = workdir

    def _resolve_path(self, path: str | None) -> Path:
        if path:
            p = Path(path)
            if not p.is_absolute() and self._workdir:
                p = Path(self._workdir) / p
            return p
        if self._workdir:
            return Path(self._workdir)
        return Path.cwd()

    async def execute(self, **kwargs: Any) -> str:
        pattern: str = kwargs["pattern"]
        path = kwargs.get("path")
        glob_filter: str | None = kwargs.get("glob")
        case_insensitive = bool(kwargs.get("-i", False))
        # Default n=True in content mode
        show_line_numbers = kwargs.get("-n")
        output_mode: str = kwargs.get("output_mode") or "files_with_matches"
        context = kwargs.get("context")

        if output_mode not in ("content", "files_with_matches", "count"):
            return f"Error: invalid output_mode '{output_mode}'."

        if show_line_numbers is None:
            show_line_numbers = (output_mode == "content")

        root = self._resolve_path(path)
        if not root.exists():
            return f"Error: path does not exist: {root}"

        rg = shutil.which("rg")
        if rg:
            return await self._run_rg(
                rg=rg,
                pattern=pattern,
                root=root,
                glob_filter=glob_filter,
                case_insensitive=case_insensitive,
                show_line_numbers=bool(show_line_numbers),
                output_mode=output_mode,
                context=context,
            )
        return self._run_python(
            pattern=pattern,
            root=root,
            glob_filter=glob_filter,
            case_insensitive=case_insensitive,
            show_line_numbers=bool(show_line_numbers),
            output_mode=output_mode,
            context=context,
        )

    # ---- ripgrep backend -----------------------------------------------------

    async def _run_rg(
        self,
        *,
        rg: str,
        pattern: str,
        root: Path,
        glob_filter: str | None,
        case_insensitive: bool,
        show_line_numbers: bool,
        output_mode: str,
        context: int | None,
    ) -> str:
        args: list[str] = [rg, "--color", "never"]
        if case_insensitive:
            args.append("-i")
        if glob_filter:
            args.extend(["--glob", glob_filter])

        if output_mode == "files_with_matches":
            args.append("-l")
        elif output_mode == "count":
            args.append("-c")
        else:  # content
            if show_line_numbers:
                args.append("-n")
            else:
                args.append("-N")
            if context and context > 0:
                args.extend(["-C", str(context)])

        args.extend(["--", pattern, str(root)])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        stdout = stdout_bytes.decode(errors="replace")

        # rg: 0 = matches, 1 = no matches, 2 = error
        if proc.returncode == 1 or (proc.returncode == 0 and not stdout.strip()):
            return f"No matches for '{pattern}' under {root}."
        if proc.returncode not in (0, 1):
            err = stderr_bytes.decode(errors="replace").strip() or "unknown error"
            return f"Error: rg exited {proc.returncode}: {err}"

        # Strip the root prefix so paths are relative (matches Python fallback).
        stdout = _rewrite_paths_relative(stdout, root)
        return _truncate(stdout.rstrip("\n"))

    # ---- Python fallback -----------------------------------------------------

    def _run_python(
        self,
        *,
        pattern: str,
        root: Path,
        glob_filter: str | None,
        case_insensitive: bool,
        show_line_numbers: bool,
        output_mode: str,
        context: int | None,
    ) -> str:
        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return f"Error: invalid regex: {exc}"

        # Collect candidate files.
        if root.is_file():
            files: list[Path] = [root]
        else:
            files = [p for p in root.rglob("*") if p.is_file()]

        if glob_filter:
            files = [p for p in files if _fnmatch_any(p, root, glob_filter)]

        out_lines: list[str] = []
        files_with_matches: list[Path] = []
        count_per_file: dict[Path, int] = {}
        total_chars = 0
        truncated = False

        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            lines = text.splitlines()
            matched_line_idxs: list[int] = [
                i for i, line in enumerate(lines) if regex.search(line)
            ]
            if not matched_line_idxs:
                continue

            if output_mode == "files_with_matches":
                files_with_matches.append(fp)
                continue
            if output_mode == "count":
                count_per_file[fp] = len(matched_line_idxs)
                continue

            # content mode
            rel = _relative(fp, root)
            emit_idxs = _expand_context(matched_line_idxs, context or 0, len(lines))
            for idx in emit_idxs:
                line = lines[idx]
                if show_line_numbers:
                    piece = f"{rel}:{idx + 1}:{line}"
                else:
                    piece = f"{rel}:{line}"
                out_lines.append(piece)
                total_chars += len(piece) + 1
                if total_chars > _MAX_OUTPUT:
                    truncated = True
                    break
            if truncated:
                break

        if output_mode == "files_with_matches":
            if not files_with_matches:
                return f"No matches for '{pattern}' under {root}."
            rels = [str(_relative(p, root)) for p in files_with_matches]
            return _truncate("\n".join(rels))

        if output_mode == "count":
            if not count_per_file:
                return f"No matches for '{pattern}' under {root}."
            rels = [f"{_relative(p, root)}:{n}" for p, n in count_per_file.items()]
            return _truncate("\n".join(rels))

        # content
        if not out_lines:
            return f"No matches for '{pattern}' under {root}."
        result = "\n".join(out_lines)
        if truncated or len(result) > _MAX_OUTPUT:
            return result[:_MAX_OUTPUT] + _TRUNCATE_MARKER
        return result


# -- helpers -------------------------------------------------------------------

def _relative(p: Path, root: Path) -> Path:
    try:
        return p.relative_to(root)
    except ValueError:
        # root is a file or p lives elsewhere — fall back to absolute
        if root.is_file() and p == root:
            return Path(p.name)
        return p


def _fnmatch_any(p: Path, root: Path, pattern: str) -> bool:
    """Match against both basename and the path relative to root."""
    name = p.name
    rel = str(_relative(p, root))
    return fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern)


def _expand_context(matched: list[int], ctx: int, total_lines: int) -> list[int]:
    if ctx <= 0:
        return matched
    wanted: set[int] = set()
    for i in matched:
        lo = max(0, i - ctx)
        hi = min(total_lines - 1, i + ctx)
        wanted.update(range(lo, hi + 1))
    return sorted(wanted)


def _rewrite_paths_relative(stdout: str, root: Path) -> str:
    """If rg emitted absolute paths rooted at `root`, strip the prefix."""
    if not stdout:
        return stdout
    prefix = str(root)
    if not prefix.endswith("/"):
        prefix_slash = prefix + "/"
    else:
        prefix_slash = prefix
    out_lines: list[str] = []
    for line in stdout.splitlines():
        if line.startswith(prefix_slash):
            out_lines.append(line[len(prefix_slash):])
        elif line == prefix:
            out_lines.append(Path(prefix).name)
        else:
            out_lines.append(line)
    return "\n".join(out_lines)
