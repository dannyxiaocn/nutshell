"""Tests for the built-in bash tool (now in toolhub/bash/)."""
import pytest
from toolhub.bash.executor import BashExecutor
from butterfly.tool_engine.loader import ToolLoader
from butterfly.core.tool import Tool


def _make_bash_tool(**kwargs) -> Tool:
    """Create a bash Tool from the toolhub executor."""
    executor = BashExecutor(**kwargs)

    async def _impl(**kw) -> str:
        return await executor.execute(**kw)

    return Tool(
        name="bash",
        description="Run a bash command",
        func=_impl,
        schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "number"},
                "workdir": {"type": "string"},
                "pty": {"type": "boolean"},
            },
            "required": ["command"],
        },
    )


def test_bash_executor_is_importable():
    assert BashExecutor is not None


def test_bash_tool_schema():
    t = _make_bash_tool()
    props = t.schema["properties"]
    assert "command" in props
    assert "timeout" in props
    assert "workdir" in props
    assert "pty" in props
    assert t.schema["required"] == ["command"]


@pytest.mark.asyncio
async def test_basic_echo():
    t = _make_bash_tool()
    result = await t.execute(command="echo hello")
    assert "hello" in result
    assert "[exit 0]" in result


@pytest.mark.asyncio
async def test_stderr_merged():
    t = _make_bash_tool()
    result = await t.execute(command="echo err >&2")
    assert "err" in result
    assert "[exit 0]" in result


@pytest.mark.asyncio
async def test_nonzero_exit_code():
    t = _make_bash_tool()
    result = await t.execute(command="exit 7")
    assert "[exit 7]" in result


@pytest.mark.asyncio
async def test_timeout():
    t = _make_bash_tool()
    result = await t.execute(command="sleep 60", timeout=0.3)
    assert "timed out" in result.lower()


@pytest.mark.asyncio
async def test_workdir(tmp_path):
    t = _make_bash_tool()
    result = await t.execute(command="pwd", workdir=str(tmp_path))
    assert str(tmp_path) in result


@pytest.mark.asyncio
async def test_output_truncation():
    t = _make_bash_tool(max_output=50)
    result = await t.execute(command="python3 -c \"print('x' * 200)\"")
    assert "truncated" in result


@pytest.mark.asyncio
async def test_factory_default_workdir(tmp_path):
    t = _make_bash_tool(workdir=str(tmp_path))
    result = await t.execute(command="pwd")
    assert str(tmp_path) in result


@pytest.mark.asyncio
async def test_pty_basic():
    t = _make_bash_tool()
    result = await t.execute(command="echo pty-hello", pty=True)
    if "[pty unavailable" in result:
        pytest.skip("PTY not available in this environment")
    assert "pty-hello" in result
    assert "[exit 0]" in result


@pytest.mark.asyncio
async def test_pty_exit_code():
    t = _make_bash_tool()
    result = await t.execute(command="exit 3", pty=True)
    if "[pty unavailable" in result:
        pytest.skip("PTY not available in this environment")
    assert "[exit 3]" in result


@pytest.mark.asyncio
async def test_pty_timeout():
    t = _make_bash_tool()
    result = await t.execute(command="sleep 60", timeout=0.3, pty=True)
    if "[pty unavailable" in result:
        pytest.skip("PTY not available in this environment")
    assert "timed out" in result.lower()


# ── ToolLoader default_workdir ─────────────────────────────────────────────────

def test_toolloader_bash_uses_default_workdir(tmp_path):
    """ToolLoader.load() for bash tool uses default_workdir."""
    import json
    bash_json = tmp_path / "tools" / "bash.json"
    bash_json.parent.mkdir()
    bash_json.write_text(json.dumps({
        "name": "bash",
        "description": "run bash",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }))
    workdir = tmp_path / "session"
    workdir.mkdir()
    loader = ToolLoader(default_workdir=str(workdir))
    tool = loader.load(bash_json)
    assert tool.name == "bash"
    import asyncio
    result = asyncio.run(tool.execute(command="pwd"))
    assert str(workdir) in result


def test_toolloader_shell_uses_default_workdir(tmp_path):
    """ToolLoader.default_workdir is passed to ShellExecutor for agent-created tools."""
    import json
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()

    sh = tools_dir / "show_pwd.sh"
    sh.write_text("#!/usr/bin/env bash\npwd\n")
    sh.chmod(0o755)
    json_def = tools_dir / "show_pwd.json"
    json_def.write_text(json.dumps({
        "name": "show_pwd",
        "description": "print cwd",
        "input_schema": {"type": "object", "properties": {}},
    }))

    session_dir = tmp_path / "session"
    session_dir.mkdir()

    loader = ToolLoader(default_workdir=str(session_dir))
    tool = loader.load(json_def)
    import asyncio
    result = asyncio.run(tool.execute())
    assert str(session_dir) in result
