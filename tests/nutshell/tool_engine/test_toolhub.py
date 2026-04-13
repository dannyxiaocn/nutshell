"""Tests for toolhub tools: manage_task, recall_memory, web_search, and ToolLoader toolhub integration."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from nutshell.tool_engine.loader import (
    ToolLoader,
    _load_tool_schema,
    _read_tool_md,
)


# ── manage_task executor ─────────────────────────────────────────────────────


class TestManageTaskExecutor:
    @pytest.fixture
    def executor(self, tmp_path):
        from toolhub.manage_task.executor import ManageTaskExecutor
        return ManageTaskExecutor(tasks_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_list_empty(self, executor):
        result = await executor.execute(action="list")
        assert "No tasks found" in result

    @pytest.mark.asyncio
    async def test_create_and_list(self, executor, tmp_path):
        result = await executor.execute(action="create", name="test_task", description="Do stuff")
        assert "created" in result

        result = await executor.execute(action="list")
        assert "test_task" in result
        assert "Do stuff" in result

    @pytest.mark.asyncio
    async def test_create_duplicate_fails(self, executor):
        await executor.execute(action="create", name="dup")
        result = await executor.execute(action="create", name="dup")
        assert "already exists" in result

    @pytest.mark.asyncio
    async def test_update(self, executor):
        await executor.execute(action="create", name="upd", description="old")
        result = await executor.execute(action="update", name="upd", description="new")
        assert "updated" in result

        data = json.loads((executor._tasks_dir / "upd.json").read_text())
        assert data["description"] == "new"

    @pytest.mark.asyncio
    async def test_pause_and_finish(self, executor):
        await executor.execute(action="create", name="pf")

        result = await executor.execute(action="finish", name="pf")
        assert "finished" in result

        data = json.loads((executor._tasks_dir / "pf.json").read_text())
        assert data["status"] == "finished"
        assert data["last_finished_at"] is not None

        result = await executor.execute(action="pause", name="pf")
        assert "paused" in result

    @pytest.mark.asyncio
    async def test_missing_name_error(self, executor):
        result = await executor.execute(action="create")
        assert "required" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_unknown_action_error(self, executor):
        result = await executor.execute(action="unknown")
        assert "unknown" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_no_tasks_dir_error(self):
        from toolhub.manage_task.executor import ManageTaskExecutor
        executor = ManageTaskExecutor(tasks_dir=None)
        result = await executor.execute(action="list")
        assert "not configured" in result


# ── recall_memory executor ───────────────────────────────────────────────────


class TestRecallMemoryExecutor:
    @pytest.fixture
    def executor(self, tmp_path):
        from toolhub.recall_memory.executor import RecallMemoryExecutor
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "facts.md").write_text("Important fact 1\nFact 2")
        (memory_dir / "empty.md").write_text("")
        return RecallMemoryExecutor(memory_dir=memory_dir)

    @pytest.mark.asyncio
    async def test_list_layers(self, executor):
        result = await executor.execute()
        assert "facts" in result
        # Empty file should not appear
        assert "empty" not in result

    @pytest.mark.asyncio
    async def test_read_layer(self, executor):
        result = await executor.execute(name="facts")
        assert "Important fact 1" in result
        assert "# Memory: facts" in result

    @pytest.mark.asyncio
    async def test_read_missing_layer(self, executor):
        result = await executor.execute(name="nonexistent")
        assert "not found" in result
        assert "facts" in result  # should suggest available

    @pytest.mark.asyncio
    async def test_read_empty_layer(self, executor):
        result = await executor.execute(name="empty")
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_no_memory_dir_error(self):
        from toolhub.recall_memory.executor import RecallMemoryExecutor
        executor = RecallMemoryExecutor(memory_dir=None)
        result = await executor.execute()
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_sanitizes_path_traversal(self, executor):
        result = await executor.execute(name="../../../etc/passwd")
        assert "not found" in result

    def test_schema_allows_empty_name_for_listing(self):
        """tool.json must not require 'name' so the LLM can list layers."""
        schema = _load_tool_schema("recall_memory")
        assert schema is not None
        required = schema.get("input_schema", {}).get("required", [])
        assert "name" not in required


# ── web_search executor ──────────────────────────────────────────────────────


class TestWebSearchExecutor:
    def test_web_search_executor_instantiates(self):
        from toolhub.web_search.executor import WebSearchExecutor
        executor = WebSearchExecutor(provider="brave")
        assert executor._provider == "brave"

    def test_web_search_executor_default_brave(self):
        from toolhub.web_search.executor import WebSearchExecutor
        executor = WebSearchExecutor()
        assert executor._provider == "brave"


# ── ToolLoader toolhub integration ───────────────────────────────────────────


class TestToolLoaderToolhub:
    def test_load_tool_schema_from_toolhub(self):
        """_load_tool_schema loads tool.json from the real toolhub."""
        schema = _load_tool_schema("bash")
        assert schema is not None
        assert schema["name"] == "bash"
        assert "input_schema" in schema

    def test_load_tool_schema_missing(self, tmp_path):
        """_load_tool_schema returns None for missing tool."""
        schema = _load_tool_schema("nonexistent", toolhub_dir=tmp_path)
        assert schema is None

    def test_read_tool_md(self, tmp_path):
        """_read_tool_md reads a tool.md file."""
        tool_md = tmp_path / "tool.md"
        tool_md.write_text("bash\nweb_search\n# comment\n\nskill\n")
        names = _read_tool_md(tool_md)
        assert names == ["bash", "web_search", "skill"]

    def test_read_tool_md_missing(self, tmp_path):
        """_read_tool_md returns empty for missing file."""
        names = _read_tool_md(tmp_path / "nonexistent")
        assert names == []

    def test_load_from_tool_md(self, tmp_path):
        """ToolLoader.load_from_tool_md loads tools listed in tool.md."""
        tool_md = tmp_path / "tool.md"
        tool_md.write_text("bash\n")
        loader = ToolLoader()
        tools = loader.load_from_tool_md(tool_md)
        names = [t.name for t in tools]
        assert "bash" in names

    def test_load_from_toolhub_bash(self):
        """ToolLoader.load_from_toolhub loads bash tool."""
        loader = ToolLoader()
        tool = loader.load_from_toolhub("bash")
        assert tool is not None
        assert tool.name == "bash"

    def test_load_from_toolhub_missing(self, tmp_path):
        """ToolLoader.load_from_toolhub returns None for missing tool."""
        loader = ToolLoader(toolhub_dir=tmp_path)
        tool = loader.load_from_toolhub("nonexistent")
        assert tool is None

    def test_load_local_tools(self, tmp_path):
        """ToolLoader.load_local_tools loads .json+.sh pairs."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        schema = {
            "name": "my_tool",
            "description": "A tool",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
        (tools_dir / "my_tool.json").write_text(json.dumps(schema))
        sh = tools_dir / "my_tool.sh"
        sh.write_text('#!/bin/bash\necho "ok"')
        sh.chmod(0o755)

        loader = ToolLoader()
        tools = loader.load_local_tools(tools_dir)
        assert len(tools) == 1
        assert tools[0].name == "my_tool"

    def test_load_local_tools_ignores_json_without_sh(self, tmp_path):
        """ToolLoader.load_local_tools skips .json files without matching .sh."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        schema = {"name": "orphan", "description": "No script"}
        (tools_dir / "orphan.json").write_text(json.dumps(schema))

        loader = ToolLoader()
        tools = loader.load_local_tools(tools_dir)
        assert len(tools) == 0

    def test_load_local_tools_empty_dir(self, tmp_path):
        """ToolLoader.load_local_tools returns empty for empty dir."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        loader = ToolLoader()
        assert loader.load_local_tools(tools_dir) == []

    def test_load_local_tools_nonexistent_dir(self, tmp_path):
        """ToolLoader.load_local_tools returns empty for nonexistent dir."""
        loader = ToolLoader()
        assert loader.load_local_tools(tmp_path / "nope") == []
