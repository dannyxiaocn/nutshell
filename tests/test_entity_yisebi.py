"""Tests for entity/yisebi — validate entity loading, inheritance, skill resolution."""
from __future__ import annotations

import yaml
import pytest
from pathlib import Path

ENTITY_DIR = Path(__file__).parent.parent / "entity"
YISEBI_DIR = ENTITY_DIR / "yisebi"


# ── YAML loading ──────────────────────────────────────────────────────────────

class TestAgentYaml:
    """Verify the yisebi agent.yaml is well-formed."""

    @pytest.fixture
    def manifest(self) -> dict:
        text = (YISEBI_DIR / "agent.yaml").read_text(encoding="utf-8")
        return yaml.safe_load(text)

    def test_agent_yaml_exists(self):
        assert (YISEBI_DIR / "agent.yaml").exists()

    def test_name_is_yisebi(self, manifest):
        assert manifest["name"] == "yisebi"

    def test_extends_agent(self, manifest):
        assert manifest["extends"] == "agent"

    def test_model_is_sonnet(self, manifest):
        assert manifest["model"] == "claude-sonnet-4-6"

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

    def test_has_web_search_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/web_search.json" in tools

    def test_has_fetch_url_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/fetch_url.json" in tools

    def test_no_git_checkpoint(self, manifest):
        """yisebi should NOT have dev tools."""
        tools = manifest.get("tools", [])
        assert "tools/git_checkpoint.json" not in tools

    def test_no_propose_entity_update(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/propose_entity_update.json" not in tools

    def test_no_spawn_session(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/spawn_session.json" not in tools

    def test_skills_include_social_media(self, manifest):
        skills = manifest.get("skills", [])
        assert "skills/social-media" in skills

    def test_exactly_three_tools(self, manifest):
        tools = manifest.get("tools", [])
        assert len(tools) == 3

    def test_exactly_one_skill(self, manifest):
        skills = manifest.get("skills", [])
        assert len(skills) == 1

    def test_description_mentions_social_media(self, manifest):
        desc = manifest.get("description", "")
        assert "social media" in desc.lower()


# ── System prompt ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    """Verify the system prompt content."""

    @pytest.fixture
    def prompt(self) -> str:
        return (YISEBI_DIR / "prompts" / "system.md").read_text(encoding="utf-8")

    def test_system_prompt_exists(self):
        assert (YISEBI_DIR / "prompts" / "system.md").exists()

    def test_system_prompt_not_empty(self, prompt):
        assert len(prompt.strip()) > 200

    def test_mentions_yisebi(self, prompt):
        assert "yisebi" in prompt.lower()

    def test_mentions_action_oriented(self, prompt):
        assert "行动派" in prompt or "action" in prompt.lower()

    def test_mentions_unique_perspectives(self, prompt):
        assert "独到见解" in prompt or "unique perspective" in prompt.lower()

    def test_mentions_direct_expression(self, prompt):
        assert "表达直接" in prompt or "direct" in prompt.lower()

    def test_mentions_web_search(self, prompt):
        assert "web_search" in prompt

    def test_mentions_fetch_url(self, prompt):
        assert "fetch_url" in prompt

    def test_mentions_trending(self, prompt):
        assert "trending" in prompt.lower()

    def test_mentions_comment(self, prompt):
        assert "comment" in prompt.lower()

    def test_mentions_social_media(self, prompt):
        assert "social media" in prompt.lower()

    def test_has_phased_approach(self, prompt):
        assert "phase 1" in prompt.lower() or "scout" in prompt.lower()

    def test_mentions_bash(self, prompt):
        assert "bash" in prompt.lower()


# ── Social-media skill ────────────────────────────────────────────────────────

class TestSocialMediaSkill:
    """Verify the social-media skill is well-formed."""

    SKILL_PATH = YISEBI_DIR / "skills" / "social-media" / "SKILL.md"

    def test_skill_file_exists(self):
        assert self.SKILL_PATH.exists()

    def test_skill_has_frontmatter(self):
        content = self.SKILL_PATH.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "social-media"
        assert "description" in fm

    def test_skill_mentions_trending(self):
        content = self.SKILL_PATH.read_text()
        assert "trending" in content.lower()

    def test_skill_mentions_comment(self):
        content = self.SKILL_PATH.read_text()
        assert "comment" in content.lower()

    def test_skill_mentions_engagement(self):
        content = self.SKILL_PATH.read_text()
        assert "engag" in content.lower()

    def test_skill_mentions_platform(self):
        content = self.SKILL_PATH.read_text()
        assert "platform" in content.lower()

    def test_skill_mentions_analysis(self):
        content = self.SKILL_PATH.read_text()
        assert "analy" in content.lower()

    def test_skill_mentions_twitter_or_x(self):
        content = self.SKILL_PATH.read_text()
        assert "twitter" in content.lower() or "/x" in content.lower() or "twitter / x" in content.lower()

    def test_skill_mentions_reddit(self):
        content = self.SKILL_PATH.read_text()
        assert "reddit" in content.lower()

    def test_skill_has_step_structure(self):
        content = self.SKILL_PATH.read_text()
        assert "step 1" in content.lower() or "## step" in content.lower()

    def test_skill_mentions_follow_up(self):
        content = self.SKILL_PATH.read_text()
        assert "follow" in content.lower()

    def test_skill_mentions_web_search(self):
        content = self.SKILL_PATH.read_text()
        assert "web_search" in content

    def test_skill_mentions_fetch_url(self):
        content = self.SKILL_PATH.read_text()
        assert "fetch_url" in content


# ── AgentLoader integration ──────────────────────────────────────────────────

class TestAgentLoaderIntegration:
    """Verify the yisebi entity loads through AgentLoader without errors."""

    def test_load_yisebi(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        assert agent is not None

    def test_loaded_agent_has_system_prompt(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        assert "yisebi" in agent.system_prompt.lower()

    def test_loaded_agent_has_tools(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "bash" in tool_names
        assert "web_search" in tool_names
        assert "fetch_url" in tool_names

    def test_loaded_agent_no_dev_tools(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "git_checkpoint" not in tool_names
        assert "propose_entity_update" not in tool_names
        assert "spawn_session" not in tool_names

    def test_loaded_agent_has_skills(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        skill_names = {s.name for s in agent.skills}
        assert "social-media" in skill_names

    def test_loaded_agent_inherits_heartbeat(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        assert agent.heartbeat_prompt  # inherited from agent

    def test_loaded_agent_model(self):
        from nutshell.llm_engine.loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(YISEBI_DIR)
        assert agent.model == "claude-sonnet-4-6"


# ── Entity directory structure ────────────────────────────────────────────────

class TestEntityStructure:
    """Verify directory layout matches conventions."""

    def test_entity_dir_exists(self):
        assert YISEBI_DIR.is_dir()

    def test_prompts_dir_exists(self):
        assert (YISEBI_DIR / "prompts").is_dir()

    def test_skills_dir_exists(self):
        assert (YISEBI_DIR / "skills").is_dir()

    def test_social_media_skill_dir_exists(self):
        assert (YISEBI_DIR / "skills" / "social-media").is_dir()

    def test_all_tool_refs_resolve(self):
        """Every tool path in agent.yaml should resolve through ancestor chain."""
        manifest = yaml.safe_load(
            (YISEBI_DIR / "agent.yaml").read_text()
        )
        for tool_rel in manifest.get("tools", []):
            found = (
                (YISEBI_DIR / tool_rel).exists()
                or (ENTITY_DIR / "agent" / tool_rel).exists()
            )
            assert found, f"Tool '{tool_rel}' not found in ancestor chain"

    def test_all_skill_refs_resolve(self):
        """Every skill path should resolve through ancestor chain."""
        manifest = yaml.safe_load(
            (YISEBI_DIR / "agent.yaml").read_text()
        )
        for skill_rel in manifest.get("skills", []):
            found = (
                (YISEBI_DIR / skill_rel / "SKILL.md").exists()
                or (ENTITY_DIR / "agent" / skill_rel / "SKILL.md").exists()
            )
            assert found, f"Skill '{skill_rel}' not found in ancestor chain"
