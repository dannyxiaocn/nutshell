"""Tests for the `butterfly codex login` and `butterfly kimi login` helpers."""
from __future__ import annotations

import argparse
import json
import sys

import pytest

from ui.cli import login as login_mod


# ── Codex login ─────────────────────────────────────────────────────────────


def _make_codex_args(**overrides) -> argparse.Namespace:
    base = dict(codex_cmd="login", skip_cli=False, no_verify=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_codex_login_missing_cli_prints_install_hint(monkeypatch, capsys):
    """With no codex CLI on PATH, we should print install + login instructions."""
    monkeypatch.setattr(login_mod.shutil, "which", lambda _cmd: None)
    rc = login_mod.cmd_codex(_make_codex_args())
    assert rc == 1
    out = capsys.readouterr().out
    assert "codex CLI not found" in out
    assert login_mod._CODEX_INSTALL_HINT in out
    assert "codex login" in out


def test_codex_login_skip_cli_verifies_existing_auth(monkeypatch, tmp_path, capsys):
    """--skip-cli should bypass subprocess and go straight to verification."""
    fake_auth = tmp_path / "auth.json"
    fake_auth.write_text(json.dumps({
        "tokens": {
            "access_token": "a.b.c",
            "refresh_token": "r.r.r",
            "id_token": "",
        }
    }), encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", fake_auth)
    monkeypatch.setattr(
        "butterfly.llm_engine.providers.codex._extract_account_id",
        lambda access, id_token="": "acct-123",
    )

    rc = login_mod.cmd_codex(_make_codex_args(skip_cli=True))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Codex login verified" in out
    assert "acct-123" in out


def test_codex_login_skip_cli_missing_auth_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", tmp_path / "nope.json")
    rc = login_mod.cmd_codex(_make_codex_args(skip_cli=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_codex_login_skip_cli_corrupt_auth_fails(monkeypatch, tmp_path, capsys):
    auth = tmp_path / "auth.json"
    auth.write_text("{{ not json", encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)
    rc = login_mod.cmd_codex(_make_codex_args(skip_cli=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert "could not parse" in err


def test_codex_login_skip_cli_missing_tokens_fails(monkeypatch, tmp_path, capsys):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"tokens": {"access_token": "x"}}), encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)
    rc = login_mod.cmd_codex(_make_codex_args(skip_cli=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert "missing" in err.lower()


def test_codex_login_runs_subprocess_and_verifies(monkeypatch, tmp_path, capsys):
    """Full happy path: codex CLI present, subprocess returns 0, auth verified."""
    monkeypatch.setattr(login_mod.shutil, "which", lambda _cmd: "/usr/local/bin/codex")

    called: dict[str, object] = {}

    def fake_call(argv):
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(login_mod.subprocess, "call", fake_call)

    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({
        "tokens": {"access_token": "a.b.c", "refresh_token": "r", "id_token": ""}
    }), encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)
    monkeypatch.setattr(
        "butterfly.llm_engine.providers.codex._extract_account_id",
        lambda access, id_token="": "acct-OK",
    )

    rc = login_mod.cmd_codex(_make_codex_args())
    assert rc == 0
    assert called["argv"] == ["/usr/local/bin/codex", "login"]
    assert "Codex login verified" in capsys.readouterr().out


def test_codex_login_no_verify(monkeypatch, capsys):
    monkeypatch.setattr(login_mod.shutil, "which", lambda _cmd: "/usr/local/bin/codex")
    monkeypatch.setattr(login_mod.subprocess, "call", lambda argv: 0)
    rc = login_mod.cmd_codex(_make_codex_args(no_verify=True))
    assert rc == 0
    assert "Skipping verification" in capsys.readouterr().out


def test_codex_login_subprocess_fail_propagates_rc(monkeypatch, capsys):
    monkeypatch.setattr(login_mod.shutil, "which", lambda _cmd: "/usr/local/bin/codex")
    monkeypatch.setattr(login_mod.subprocess, "call", lambda argv: 7)
    rc = login_mod.cmd_codex(_make_codex_args())
    assert rc == 7


# ── Kimi login (URL-printer only; no interactive flow) ──────────────────────


def test_kimi_login_prints_dashboard_url_and_env_var(capsys):
    args = argparse.Namespace(kimi_cmd="login")
    rc = login_mod.cmd_kimi(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert login_mod._KIMI_DASHBOARD_URL in out
    assert login_mod._KIMI_ENV_KEY in out
    # The sanctioned dashboard is the Kimi Code console, not the legacy
    # platform.moonshot.ai path that v2.0.7 used.
    assert login_mod._KIMI_DASHBOARD_URL == "https://www.kimi.com/code/console"
    assert login_mod._KIMI_ENV_KEY == "KIMI_FOR_CODING_API_KEY"


def test_kimi_login_does_not_touch_filesystem_or_env(
    monkeypatch, tmp_path, capsys
):
    """The simplified command must be pure stdout — no .env writes, no env
    mutation, no network ping."""
    # Any accidental write under tmp_path would show up as a file.
    monkeypatch.chdir(tmp_path)
    # Arrange a sentinel env var so we can detect any mutation.
    monkeypatch.delenv(login_mod._KIMI_ENV_KEY, raising=False)

    args = argparse.Namespace(kimi_cmd="login")
    rc = login_mod.cmd_kimi(args)
    assert rc == 0
    assert list(tmp_path.iterdir()) == []
    assert login_mod._KIMI_ENV_KEY not in __import__("os").environ


# ── End-to-end through argparse ─────────────────────────────────────────────


def test_main_dispatches_codex_login(monkeypatch, capsys):
    """Verify `butterfly codex login --skip-cli --no-verify` wires up correctly."""
    from ui.cli import main as main_mod

    monkeypatch.setattr(sys, "argv", ["butterfly", "codex", "login", "--skip-cli", "--no-verify"])
    with pytest.raises(SystemExit) as exc:
        main_mod.main()
    assert exc.value.code == 0
    assert "Skipping verification" in capsys.readouterr().out


def test_main_dispatches_kimi_login(monkeypatch, capsys):
    from ui.cli import main as main_mod

    monkeypatch.setattr(sys, "argv", ["butterfly", "kimi", "login"])
    with pytest.raises(SystemExit) as exc:
        main_mod.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert login_mod._KIMI_DASHBOARD_URL in out
