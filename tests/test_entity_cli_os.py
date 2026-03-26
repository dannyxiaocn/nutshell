"""Tests for the cli_os entity — directory structure, manifest, prompts, skill, loader."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ENTITY_DIR = Path(__file__).parent.parent / "entity"
CLI_OS_DIR = ENTITY_DIR / "cli_os"


# ── Manifest (agent.yaml) ────────────────────────────────────────────────────

class TestManifest:
    """Verify agent.yaml is well-formed and has the expected fields."""

    @pytest.fixture
    def manifest(self) -> dict:
        return yaml.safe_load((CLI_OS_DIR / "agent.yaml").read_text(encoding="utf-8"))

    def test_agent_yaml_exists(self):
        assert (CLI_OS_DIR / "agent.yaml").exists()

    def test_name_is_cli_os(self, manifest):
        assert manifest["name"] == "cli_os"

    def test_extends_agent(self, manifest):
        assert manifest["extends"] == "agent"

    def test_model_is_sonnet(self, manifest):
        assert manifest["model"] == "claude-sonnet-4-6"

    def test_provider_is_anthropic(self, manifest):
        assert manifest["provider"] == "anthropic"

    def test_release_policy_on_demand(self, manifest):
        assert manifest["release_policy"] == "on_demand"

    def test_max_iterations_30(self, manifest):
        assert manifest["max_iterations"] == 30

    def test_has_system_prompt_path(self, manifest):
        prompts = manifest.get("prompts", {})
        assert prompts.get("system") == "prompts/system.md"

    def test_heartbeat_interval(self, manifest):
        params = manifest.get("params", {})
        assert params.get("heartbeat_interval") == 600

    def test_persistent_false(self, manifest):
        params = manifest.get("params", {})
        assert params.get("persistent") is False

    def test_has_bash_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/bash.json" in tools

    def test_has_fetch_url_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/fetch_url.json" in tools

    def test_has_web_search_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/web_search.json" in tools

    def test_has_recall_memory_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/recall_memory.json" in tools

    def test_has_state_diff_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/state_diff.json" in tools

    def test_has_app_notify_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/app_notify.json" in tools

    def test_no_git_checkpoint(self, manifest):
        """CLI-OS should NOT have dev tools."""
        tools = manifest.get("tools", [])
        assert "tools/git_checkpoint.json" not in tools

    def test_no_propose_entity_update(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/propose_entity_update.json" not in tools

    def test_no_spawn_session(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/spawn_session.json" not in tools

    def test_skills_include_cli_explorer(self, manifest):
        skills = manifest.get("skills", [])
        assert "skills/cli-explorer" in skills

    def test_description_mentions_playground(self, manifest):
        desc = manifest.get("description", "")
        assert "playground" in desc.lower()


# ── System prompt ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    """Verify the system prompt content."""

    @pytest.fixture
    def prompt(self) -> str:
        return (CLI_OS_DIR / "prompts" / "system.md").read_text(encoding="utf-8")

    def test_system_prompt_exists(self):
        assert (CLI_OS_DIR / "prompts" / "system.md").exists()

    def test_system_prompt_not_empty(self, prompt):
        assert len(prompt.strip()) > 200

    def test_mentions_cli_os(self, prompt):
        assert "CLI-OS" in prompt

    def test_mentions_root(self, prompt):
        assert "root" in prompt.lower()

    def test_mentions_playground(self, prompt):
        assert "playground" in prompt.lower()

    def test_mentions_bash(self, prompt):
        assert "bash" in prompt.lower()

    def test_mentions_python(self, prompt):
        assert "python" in prompt.lower() or "Python" in prompt

    def test_mentions_filesystem(self, prompt):
        assert "filesystem" in prompt.lower() or "file" in prompt.lower()

    def test_mentions_workspace_layout(self, prompt):
        assert "projects/" in prompt and "tmp/" in prompt

    def test_mentions_curiosity_or_creative(self, prompt):
        assert "curious" in prompt.lower() or "creative" in prompt.lower()


# ── CLI-explorer skill ────────────────────────────────────────────────────────

class TestCliExplorerSkill:
    """Verify the cli-explorer skill is well-formed."""

    SKILL_PATH = CLI_OS_DIR / "skills" / "cli-explorer" / "SKILL.md"

    def test_skill_file_exists(self):
        assert self.SKILL_PATH.exists()

    def test_skill_has_frontmatter(self):
        content = self.SKILL_PATH.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "cli-explorer"
        assert "description" in fm

    def test_skill_mentions_discovery(self):
        content = self.SKILL_PATH.read_text()
        assert "discover" in content.lower() or "Discovery" in content

    def test_skill_mentions_workspace(self):
        content = self.SKILL_PATH.read_text()
        assert "workspace" in content.lower()

    def test_skill_mentions_project_templates(self):
        content = self.SKILL_PATH.read_text()
        assert "template" in content.lower() or "Template" in content

    def test_skill_has_code_examples(self):
        content = self.SKILL_PATH.read_text()
        assert "```bash" in content or "```python" in content

    def test_skill_mentions_cleanup(self):
        content = self.SKILL_PATH.read_text()
        assert "clean" in content.lower()

    def test_skill_mentions_git(self):
        content = self.SKILL_PATH.read_text()
        assert "git" in content.lower()

    def test_skill_mentions_state_diff(self):
        content = self.SKILL_PATH.read_text()
        assert "state_diff" in content

    def test_skill_mentions_fetch_url(self):
        content = self.SKILL_PATH.read_text()
        assert "fetch_url" in content


# ── AgentLoader integration ──────────────────────────────────────────────────

class TestAgentLoaderIntegration:
    """Verify the cli_os entity loads through AgentLoader without errors."""

    def test_load_cli_os(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        assert agent is not None

    def test_loaded_agent_has_system_prompt(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        assert "CLI-OS" in agent.system_prompt

    def test_loaded_agent_has_bash_tool(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "bash" in tool_names

    def test_loaded_agent_has_fetch_url_tool(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "fetch_url" in tool_names

    def test_loaded_agent_no_dev_tools(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "git_checkpoint" not in tool_names
        assert "propose_entity_update" not in tool_names
        assert "spawn_session" not in tool_names

    def test_loaded_agent_has_skills(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        skill_names = {s.name for s in agent.skills}
        assert "cli-explorer" in skill_names

    def test_loaded_agent_model(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        assert agent.model == "claude-sonnet-4-6"

    def test_loaded_agent_inherits_heartbeat(self):
        from nutshell.llm_engine.loader import AgentLoader
        agent = AgentLoader().load(CLI_OS_DIR)
        assert agent.heartbeat_prompt  # inherited from agent


# ── Entity directory structure ────────────────────────────────────────────────

class TestEntityStructure:
    """Verify directory layout matches conventions."""

    def test_entity_dir_exists(self):
        assert CLI_OS_DIR.is_dir()

    def test_prompts_dir_exists(self):
        assert (CLI_OS_DIR / "prompts").is_dir()

    def test_skills_dir_exists(self):
        assert (CLI_OS_DIR / "skills").is_dir()

    def test_cli_explorer_skill_dir_exists(self):
        assert (CLI_OS_DIR / "skills" / "cli-explorer").is_dir()

    def test_all_tool_refs_resolve(self):
        """Every tool path in agent.yaml should resolve through ancestor chain."""
        manifest = yaml.safe_load((CLI_OS_DIR / "agent.yaml").read_text())
        for tool_rel in manifest.get("tools", []):
            found = (
                (CLI_OS_DIR / tool_rel).exists()
                or (ENTITY_DIR / "agent" / tool_rel).exists()
            )
            assert found, f"Tool '{tool_rel}' not found in ancestor chain"

    def test_all_skill_refs_resolve(self):
        """Every skill path should resolve through ancestor chain."""
        manifest = yaml.safe_load((CLI_OS_DIR / "agent.yaml").read_text())
        for skill_rel in manifest.get("skills", []):
            found = (
                (CLI_OS_DIR / skill_rel / "SKILL.md").exists()
                or (ENTITY_DIR / "agent" / skill_rel / "SKILL.md").exists()
            )
            assert found, f"Skill '{skill_rel}' not found in ancestor chain"
