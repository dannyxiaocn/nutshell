"""Tests for GitCoordinator — master/sub role assignment for multi-agent git workflows.

Covers:
  - Master registration (first session wins)
  - Sub role for subsequent sessions
  - Release of master claims
  - Stale master reclamation
  - get_role / get_master queries
  - No-remote repos default to master
  - git_checkpoint includes role tag
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from nutshell.runtime.git_coordinator import GitCoordinator


# ── Helpers ───────────────────────────────────────────────────────────────────

def _init_git_repo(path: Path, *, remote_url: str | None = None) -> None:
    """Create a git repo with an initial commit and optional remote."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=str(path), check=True, capture_output=True)
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"],
                   cwd=str(path), check=True, capture_output=True)
    if remote_url:
        subprocess.run(["git", "remote", "add", "origin", remote_url],
                       cwd=str(path), check=True, capture_output=True)


def _make_alive_session(system_base: Path, session_id: str) -> None:
    """Create a fake session dir with status.json showing current PID (alive)."""
    sess_dir = system_base / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    (sess_dir / "status.json").write_text(json.dumps({"pid": os.getpid()}))


def _make_dead_session(system_base: Path, session_id: str) -> None:
    """Create a fake session dir with status.json showing a non-existent PID."""
    sess_dir = system_base / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    # Use a PID that almost certainly doesn't exist
    (sess_dir / "status.json").write_text(json.dumps({"pid": 99999999}))


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGitCoordinatorRegistration:
    """Test master/sub registration logic."""

    def test_first_session_becomes_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")

        gc = GitCoordinator(system_base=system_base)
        role = gc.register(repo, "sess-1")
        assert role == "master"

    def test_second_session_becomes_sub(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")
        _make_alive_session(system_base, "sess-2")

        gc = GitCoordinator(system_base=system_base)
        role1 = gc.register(repo, "sess-1")
        role2 = gc.register(repo, "sess-2")
        assert role1 == "master"
        assert role2 == "sub"

    def test_same_session_re_registers_as_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")

        gc = GitCoordinator(system_base=system_base)
        role1 = gc.register(repo, "sess-1")
        role2 = gc.register(repo, "sess-1")
        assert role1 == "master"
        assert role2 == "master"

    def test_no_remote_defaults_to_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo)  # no remote
        system_base = tmp_path / "_sessions"

        gc = GitCoordinator(system_base=system_base)
        role = gc.register(repo, "sess-1")
        assert role == "master"

    def test_no_session_id_returns_sub(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NUTSHELL_SESSION_ID", raising=False)
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"

        gc = GitCoordinator(system_base=system_base)
        role = gc.register(repo, "")
        assert role == "sub"


class TestGitCoordinatorRelease:
    """Test master release logic."""

    def test_release_clears_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "sess-1")
        released = gc.release("sess-1")
        assert len(released) == 1
        assert "https://github.com/test/repo.git" in released[0]

    def test_after_release_new_session_becomes_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")
        _make_alive_session(system_base, "sess-2")

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "sess-1")
        gc.release("sess-1")
        role = gc.register(repo, "sess-2")
        assert role == "master"

    def test_release_non_master_returns_empty(self, tmp_path):
        system_base = tmp_path / "_sessions"
        gc = GitCoordinator(system_base=system_base)
        released = gc.release("nonexistent-sess")
        assert released == []

    def test_release_empty_session_id(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NUTSHELL_SESSION_ID", raising=False)
        system_base = tmp_path / "_sessions"
        gc = GitCoordinator(system_base=system_base)
        released = gc.release("")
        assert released == []


class TestGitCoordinatorStaleReclamation:
    """Test that stale master sessions are automatically reclaimed."""

    def test_dead_master_is_reclaimed(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_dead_session(system_base, "dead-sess")
        _make_alive_session(system_base, "new-sess")

        gc = GitCoordinator(system_base=system_base)
        # Dead session registers as master
        gc.register(repo, "dead-sess")
        # Now dead-sess's PID doesn't exist — new session should reclaim
        role = gc.register(repo, "new-sess")
        assert role == "master"

    def test_no_status_json_treated_as_dead(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        # Create a session dir without status.json
        (system_base / "ghost-sess").mkdir(parents=True)

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "ghost-sess")
        # ghost-sess has no status.json — should be reclaimable
        role = gc.register(repo, "new-sess")
        assert role == "master"


class TestGitCoordinatorQueries:
    """Test get_role and get_master query methods."""

    def test_get_role_after_register(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "sess-1")
        assert gc.get_role(repo, "sess-1") == "master"
        assert gc.get_role(repo, "sess-2") == "sub"

    def test_get_master(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "sess-1")
        assert gc.get_master(repo) == "sess-1"

    def test_get_master_no_registration(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"

        gc = GitCoordinator(system_base=system_base)
        assert gc.get_master(repo) is None

    def test_get_role_no_remote(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo)  # no remote
        system_base = tmp_path / "_sessions"

        gc = GitCoordinator(system_base=system_base)
        assert gc.get_role(repo) == "master"


class TestGitCoordinatorRegistry:
    """Test registry file persistence."""

    def test_registry_file_created(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"

        gc = GitCoordinator(system_base=system_base)
        gc.register(repo, "sess-1")

        registry_path = system_base / "git_masters.json"
        assert registry_path.exists()
        data = json.loads(registry_path.read_text())
        assert "https://github.com/test/repo.git" in data
        assert data["https://github.com/test/repo.git"]["session_id"] == "sess-1"

    def test_registry_survives_reload(self, tmp_path):
        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        system_base = tmp_path / "_sessions"

        gc1 = GitCoordinator(system_base=system_base)
        gc1.register(repo, "sess-1")

        # New coordinator instance reads from same file
        gc2 = GitCoordinator(system_base=system_base)
        assert gc2.get_master(repo) == "sess-1"

    def test_corrupt_registry_handled(self, tmp_path):
        system_base = tmp_path / "_sessions"
        system_base.mkdir(parents=True)
        (system_base / "git_masters.json").write_text("NOT JSON!!!")

        repo = tmp_path / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")

        gc = GitCoordinator(system_base=system_base)
        # Should not crash, starts fresh
        role = gc.register(repo, "sess-1")
        assert role == "master"

    def test_multiple_repos_tracked(self, tmp_path):
        system_base = tmp_path / "_sessions"
        _make_alive_session(system_base, "sess-1")
        _make_alive_session(system_base, "sess-2")

        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        _init_git_repo(repo_a, remote_url="https://github.com/test/a.git")
        _init_git_repo(repo_b, remote_url="https://github.com/test/b.git")

        gc = GitCoordinator(system_base=system_base)
        assert gc.register(repo_a, "sess-1") == "master"
        assert gc.register(repo_b, "sess-2") == "master"
        assert gc.get_master(repo_a) == "sess-1"
        assert gc.get_master(repo_b) == "sess-2"


class TestGitCheckpointRoleTag:
    """Test that git_checkpoint includes role tag in output."""

    @pytest.mark.asyncio
    async def test_commit_includes_role_tag(self, tmp_path, monkeypatch):
        from nutshell.tool_engine.providers.git_checkpoint import git_checkpoint

        sessions_base = tmp_path / "sessions"
        session_dir = sessions_base / "test-sess"
        repo = session_dir / "playground" / "repo"
        _init_git_repo(repo, remote_url="https://github.com/test/repo.git")
        monkeypatch.setenv("NUTSHELL_SESSION_ID", "test-sess")

        # Create _sessions dir for git coordinator
        system_base = tmp_path / "_sessions"
        system_base.mkdir(parents=True)
        # Patch the _REPO_ROOT so git_checkpoint finds _sessions
        import nutshell.tool_engine.providers.git_checkpoint as gcp
        monkeypatch.setattr(gcp, "_REPO_ROOT", tmp_path)

        (repo / "new_file.txt").write_text("hello\n")
        result = await git_checkpoint(
            message="feat: test role tag",
            workdir="playground/repo",
            _sessions_base=sessions_base,
        )
        assert "Committed" in result
        assert "[git:master]" in result

    @pytest.mark.asyncio
    async def test_commit_without_remote_shows_master(self, tmp_path, monkeypatch):
        from nutshell.tool_engine.providers.git_checkpoint import git_checkpoint

        sessions_base = tmp_path / "sessions"
        session_dir = sessions_base / "test-sess"
        repo = session_dir / "playground" / "repo"
        _init_git_repo(repo)  # no remote
        monkeypatch.setenv("NUTSHELL_SESSION_ID", "test-sess")

        system_base = tmp_path / "_sessions"
        system_base.mkdir(parents=True)
        import nutshell.tool_engine.providers.git_checkpoint as gcp
        monkeypatch.setattr(gcp, "_REPO_ROOT", tmp_path)

        (repo / "file.txt").write_text("data\n")
        result = await git_checkpoint(
            message="feat: no remote",
            workdir="playground/repo",
            _sessions_base=sessions_base,
        )
        assert "Committed" in result
        assert "[git:master]" in result
