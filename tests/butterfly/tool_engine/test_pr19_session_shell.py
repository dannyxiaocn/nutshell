"""PR #19 review coverage: persistent session_shell executor."""
from __future__ import annotations

import asyncio
import sys

import pytest

from butterfly.tool_engine.executor.terminal.session_shell import SessionShellExecutor


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_persists_cwd(tmp_path) -> None:
    ex = SessionShellExecutor(workdir=str(tmp_path))
    r1 = await ex.execute(command="cd /tmp")
    assert "[exit 0" in r1
    r2 = await ex.execute(command="pwd")
    assert "/tmp" in r2
    assert "[exit 0" in r2


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_persists_env(tmp_path) -> None:
    ex = SessionShellExecutor(workdir=str(tmp_path))
    r1 = await ex.execute(command="export BFY_TEST_PERSIST=hello_there")
    assert "[exit 0" in r1
    r2 = await ex.execute(command="echo $BFY_TEST_PERSIST")
    assert "hello_there" in r2


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_captures_nonzero_exit(tmp_path) -> None:
    ex = SessionShellExecutor(workdir=str(tmp_path))
    # Run in a subshell so `exit 7` doesn't kill the persistent shell itself.
    out = await ex.execute(command="(exit 7)", timeout=5)
    assert "[exit 7" in out


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_timeout_restarts(tmp_path) -> None:
    ex = SessionShellExecutor(workdir=str(tmp_path))
    # sleep 10 with a 1s timeout — should be interrupted or killed fast.
    out = await ex.execute(command="sleep 10", timeout=1)
    assert "timed out after 1" in out
    # Next call should succeed (shell either survived the SIGINT or was restarted).
    out2 = await ex.execute(command="echo after", timeout=5)
    assert "after" in out2
    assert "[exit 0" in out2


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_timeout_zero_regression(tmp_path) -> None:
    """Cubic P2 (confirmed): `timeout=0` is silently replaced with 60.0.

    `float(kwargs.get("timeout") or 60.0)` treats 0 as falsy — the caller's
    explicit "time out immediately" request is ignored. Document via xfail
    until the fix swaps in an explicit `None` check.
    """
    ex = SessionShellExecutor(workdir=str(tmp_path))
    # With a true zero timeout, the command should time out immediately.
    # The bug makes it fall back to 60s so `sleep 2` actually succeeds.
    out = await ex.execute(command="sleep 2", timeout=0)
    if "[exit 0" in out:
        pytest.xfail(
            "SessionShellExecutor swaps timeout=0 for 60.0 (cubic P2, not fixed in PR #19)."
        )
    else:
        assert "timed out" in out


@pytest.mark.skipif(sys.platform == "win32", reason="bash required")
@pytest.mark.asyncio
async def test_session_shell_reset(tmp_path) -> None:
    ex = SessionShellExecutor(workdir=str(tmp_path))
    await ex.execute(command="export BFY_RESET_ME=42")
    r = await ex.execute(command="echo $BFY_RESET_ME")
    assert "42" in r
    reset = await ex.execute(command="", reset=True)
    assert "reset" in reset.lower()
    r2 = await ex.execute(command="echo _${BFY_RESET_ME}_")
    # After reset, the variable should be unset.
    assert "_42_" not in r2
    assert "__" in r2
