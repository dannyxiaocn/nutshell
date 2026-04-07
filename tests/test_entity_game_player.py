"""Tests for entity/game_player — validate entity loading, inheritance, skill resolution."""
from __future__ import annotations

import yaml
import pytest
from pathlib import Path

ENTITY_DIR = Path(__file__).parent.parent / "entity"
GAME_PLAYER_DIR = ENTITY_DIR / "game_player"


# ── YAML loading ──────────────────────────────────────────────────────────────

class TestAgentYaml:
    """Verify the game_player agent.yaml is well-formed."""

    @pytest.fixture
    def manifest(self) -> dict:
        text = (GAME_PLAYER_DIR / "agent.yaml").read_text(encoding="utf-8")
        return yaml.safe_load(text)

    def test_agent_yaml_exists(self):
        assert (GAME_PLAYER_DIR / "agent.yaml").exists()

    def test_name_is_game_player(self, manifest):
        assert manifest["name"] == "game_player"

    def test_extends_agent(self, manifest):
        assert manifest["extends"] == "agent"

    def test_model_is_sonnet(self, manifest):
        assert manifest["model"] == "claude-sonnet-4-6"

    def test_has_system_prompt_path(self, manifest):
        prompts = manifest.get("prompts", {})
        assert prompts.get("system") == "prompts/system.md"

    def test_heartbeat_interval(self, manifest):
        params = manifest.get("params", {})
        assert params.get("heartbeat_interval") == 300

    def test_persistent_false(self, manifest):
        params = manifest.get("params", {})
        assert params.get("persistent") is False

    def test_has_bash_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/bash.json" in tools

    def test_has_web_search_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/web_search.json" in tools

    def test_has_state_diff_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/state_diff.json" in tools

    def test_has_send_to_session_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/send_to_session.json" in tools

    def test_has_fetch_url_tool(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/fetch_url.json" in tools

    def test_no_git_checkpoint(self, manifest):
        """Game player should NOT have dev tools."""
        tools = manifest.get("tools", [])
        assert "tools/git_checkpoint.json" not in tools

    def test_no_propose_entity_update(self, manifest):
        tools = manifest.get("tools", [])
        assert "tools/propose_entity_update.json" not in tools

    def test_no_spawn_session(self, manifest):
        """Game player doesn't need to spawn sub-agents."""
        tools = manifest.get("tools", [])
        assert "tools/spawn_session.json" not in tools

    def test_skills_include_game_strategy(self, manifest):
        skills = manifest.get("skills", [])
        assert "skills/game-strategy" in skills

    def test_skills_include_multi_agent(self, manifest):
        skills = manifest.get("skills", [])
        assert "skills/multi-agent" in skills


# ── System prompt ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    """Verify the system prompt content."""

    @pytest.fixture
    def prompt(self) -> str:
        return (GAME_PLAYER_DIR / "prompts" / "system.md").read_text(encoding="utf-8")

    def test_system_prompt_exists(self):
        assert (GAME_PLAYER_DIR / "prompts" / "system.md").exists()

    def test_system_prompt_not_empty(self, prompt):
        assert len(prompt.strip()) > 200  # substantial prompt

    def test_mentions_game_player(self, prompt):
        assert "game player" in prompt.lower()

    def test_mentions_speedrun(self, prompt):
        assert "speedrun" in prompt.lower()

    def test_mentions_pattern_recognition(self, prompt):
        assert "pattern recognition" in prompt.lower()

    def test_mentions_state_diff(self, prompt):
        assert "state_diff" in prompt

    def test_mentions_text_adventures(self, prompt):
        assert "text adventure" in prompt.lower()

    def test_mentions_puzzles(self, prompt):
        assert "puzzle" in prompt.lower()

    def test_mentions_code_golf(self, prompt):
        assert "code golf" in prompt.lower()

    def test_mentions_strategy(self, prompt):
        assert "strateg" in prompt.lower()

    def test_has_phased_approach(self, prompt):
        """Prompt should describe a multi-phase game-playing approach."""
        assert "phase 1" in prompt.lower() or "recon" in prompt.lower()

    def test_mentions_bash_for_computation(self, prompt):
        assert "bash" in prompt.lower()


# ── Game-strategy skill ──────────────────────────────────────────────────────

class TestGameStrategySkill:
    """Verify the game-strategy skill is well-formed."""

    SKILL_PATH = GAME_PLAYER_DIR / "skills" / "game-strategy" / "SKILL.md"

    def test_skill_file_exists(self):
        assert self.SKILL_PATH.exists()

    def test_skill_has_frontmatter(self):
        content = self.SKILL_PATH.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "game-strategy"
        assert "description" in fm

    def test_skill_mentions_classification(self):
        content = self.SKILL_PATH.read_text()
        assert "classif" in content.lower()

    def test_skill_mentions_maze(self):
        content = self.SKILL_PATH.read_text()
        assert "maze" in content.lower() or "graph" in content.lower()

    def test_skill_mentions_permutation(self):
        content = self.SKILL_PATH.read_text()
        assert "permutation" in content.lower()

    def test_skill_mentions_word_guessing(self):
        content = self.SKILL_PATH.read_text()
        assert "word" in content.lower()

    def test_skill_mentions_math(self):
        content = self.SKILL_PATH.read_text()
        assert "math" in content.lower()

    def test_skill_mentions_state_diff(self):
        content = self.SKILL_PATH.read_text()
        assert "state_diff" in content

    def test_skill_has_code_examples(self):
        content = self.SKILL_PATH.read_text()
        assert "```python" in content

    def test_skill_mentions_brute_force(self):
        content = self.SKILL_PATH.read_text()
        assert "brute force" in content.lower() or "brute_force" in content.lower()

    def test_skill_mentions_backtracking(self):
        content = self.SKILL_PATH.read_text()
        assert "backtrack" in content.lower()

    def test_skill_has_information_types(self):
        """Skill should classify games by information completeness."""
        content = self.SKILL_PATH.read_text()
        assert "perfect information" in content.lower() or "imperfect information" in content.lower()


# ── AgentLoader integration ──────────────────────────────────────────────────

class TestAgentLoaderIntegration:
    """Verify the game_player entity loads through AgentLoader without errors."""

    def test_load_game_player(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        assert agent is not None

    def test_loaded_agent_has_system_prompt(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        assert "game player" in agent.system_prompt.lower()

    def test_loaded_agent_has_tools(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "bash" in tool_names
        assert "web_search" in tool_names
        assert "state_diff" in tool_names

    def test_loaded_agent_no_dev_tools(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        tool_names = {t.name for t in agent.tools}
        assert "git_checkpoint" not in tool_names
        assert "propose_entity_update" not in tool_names
        assert "spawn_session" not in tool_names

    def test_loaded_agent_has_skills(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        skill_names = {s.name for s in agent.skills}
        assert "game-strategy" in skill_names
        assert "multi-agent" in skill_names

    def test_loaded_agent_inherits_heartbeat(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        assert agent.heartbeat_prompt  # inherited from agent

    def test_loaded_agent_model(self):
        from nutshell.runtime.agent_loader import AgentLoader
        loader = AgentLoader()
        agent = loader.load(GAME_PLAYER_DIR)
        assert agent.model == "claude-sonnet-4-6"


# ── Entity directory structure ────────────────────────────────────────────────

class TestEntityStructure:
    """Verify directory layout matches conventions."""

    def test_entity_dir_exists(self):
        assert GAME_PLAYER_DIR.is_dir()

    def test_prompts_dir_exists(self):
        assert (GAME_PLAYER_DIR / "prompts").is_dir()

    def test_skills_dir_exists(self):
        assert (GAME_PLAYER_DIR / "skills").is_dir()

    def test_game_strategy_skill_dir_exists(self):
        assert (GAME_PLAYER_DIR / "skills" / "game-strategy").is_dir()

    def test_all_tool_refs_resolve(self):
        """Every tool path in agent.yaml should resolve through ancestor chain."""
        manifest = yaml.safe_load(
            (GAME_PLAYER_DIR / "agent.yaml").read_text()
        )
        for tool_rel in manifest.get("tools", []):
            found = (
                (GAME_PLAYER_DIR / tool_rel).exists()
                or (ENTITY_DIR / "agent" / tool_rel).exists()
            )
            assert found, f"Tool '{tool_rel}' not found in ancestor chain"

    def test_all_skill_refs_resolve(self):
        """Every skill path should resolve through ancestor chain."""
        manifest = yaml.safe_load(
            (GAME_PLAYER_DIR / "agent.yaml").read_text()
        )
        for skill_rel in manifest.get("skills", []):
            found = (
                (GAME_PLAYER_DIR / skill_rel / "SKILL.md").exists()
                or (ENTITY_DIR / "agent" / skill_rel / "SKILL.md").exists()
            )
            assert found, f"Skill '{skill_rel}' not found in ancestor chain"
