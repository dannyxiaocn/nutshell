"""Review-round regression tests for ``ui/cli/login.py`` (PR #21 review).

These cover bugs and gaps surfaced during the deep-test pass on PR #21.
Kimi-side tests were retired in v2.0.10 when ``butterfly kimi login`` was
stripped back to a URL printer — the failure modes they guarded against
(empty-key-blocks-on-getpass, secrets-file-race, legacy-env-fallback)
all became unreachable once the getpass/env-write/verify-ping flow was
removed.
"""
from __future__ import annotations

import argparse
import json

import pytest

from ui.cli import login as login_mod


# ── 1. Codex auth.json shape robustness ─────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        "[1,2,3]",         # JSON array
        '"a string"',     # JSON string
        "42",              # JSON number
        "null",            # JSON null
        "true",            # JSON bool
    ],
)
def test_codex_verify_handles_non_object_json(monkeypatch, tmp_path, capsys, payload):
    """A valid-JSON-but-non-dict auth.json should be a graceful error, not a crash."""
    auth = tmp_path / "auth.json"
    auth.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)

    # Must not raise AttributeError.
    rc = login_mod._verify_codex_auth()
    assert rc == 1, "non-object auth.json must return rc=1, not crash"
    err = capsys.readouterr().err
    assert "auth.json" in err.lower() or "missing" in err.lower() or "could not" in err.lower(), (
        f"expected an explanatory stderr message, got: {err!r}"
    )


def test_codex_verify_tokens_field_is_not_dict(monkeypatch, tmp_path, capsys):
    """If ``tokens`` is itself a non-dict (e.g. list), we shouldn't crash either."""
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"tokens": ["wrong-shape"]}), encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)

    rc = login_mod._verify_codex_auth()
    assert rc == 1


# ── 2. Codex subprocess / account-id edge cases ─────────────────────────────


def test_codex_login_subprocess_oserror_returns_1(monkeypatch, capsys):
    """If exec'ing the codex CLI itself raises OSError, we should surface it cleanly."""
    monkeypatch.setattr(login_mod.shutil, "which", lambda _cmd: "/usr/local/bin/codex")

    def boom(_argv):
        raise OSError("Exec format error")

    monkeypatch.setattr(login_mod.subprocess, "call", boom)
    rc = login_mod.cmd_codex(argparse.Namespace(
        codex_cmd="login", skip_cli=False, no_verify=True,
    ))
    assert rc == 1
    err = capsys.readouterr().err
    assert "exec" in err.lower() or "failed" in err.lower()


def test_codex_verify_account_id_extraction_failure_is_non_fatal(monkeypatch, tmp_path, capsys):
    """A failure inside ``_extract_account_id`` is decorative — verify must still pass."""
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({
        "tokens": {"access_token": "a.b.c", "refresh_token": "r", "id_token": ""}
    }), encoding="utf-8")
    monkeypatch.setattr(login_mod, "_CODEX_AUTH_PATH", auth)

    def boom(*_a, **_kw):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(
        "butterfly.llm_engine.providers.codex._extract_account_id",
        boom,
    )

    rc = login_mod._verify_codex_auth()
    assert rc == 0, "account-id failure must NOT block verify success"
    out = capsys.readouterr().out
    assert "verified" in out.lower()
