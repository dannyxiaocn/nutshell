"""One-command login helpers for Codex and Kimi providers.

Exposes two subcommands:

* ``butterfly codex login`` — drives the ``codex`` CLI's OAuth flow (or prints
  install instructions if the CLI is missing), then verifies the resulting
  ``~/.codex/auth.json`` is parseable and contains tokens.
* ``butterfly kimi login`` — prints the Kimi For Coding dashboard URL and the
  env-var name the provider reads. The user copies the key from the dashboard
  and exports it themselves (or writes it to ``.env``). No prompts, no
  verification — keeping it a plain pointer keeps the CLI stateless and
  friendly to any env-var workflow the user already has.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

_CODEX_AUTH_PATH = Path.home() / ".codex" / "auth.json"
_CODEX_INSTALL_HINT = "npm install -g @openai/codex"

_KIMI_DASHBOARD_URL = "https://www.kimi.com/code/console"
_KIMI_ENV_KEY = "KIMI_FOR_CODING_API_KEY"


# ── `butterfly codex login` ──────────────────────────────────────────────────


def _add_codex_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "codex",
        allow_abbrev=False,
        help="Codex (ChatGPT-OAuth) provider helpers.",
        description=(
            "Codex provider helpers.\n\n"
            "Subcommands:\n"
            "  butterfly codex login      Run codex OAuth login and verify auth.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    csub = p.add_subparsers(dest="codex_cmd", metavar="COMMAND")
    csub.required = True

    login = csub.add_parser(
        "login",
        allow_abbrev=False,
        help="Run the Codex CLI OAuth login and verify credentials.",
        description=(
            "One-command Codex OAuth login.\n\n"
            "Step 1: ensure the `codex` CLI is installed.\n"
            "Step 2: shell out to `codex login` to run the OAuth flow.\n"
            "Step 3: read ~/.codex/auth.json and confirm the access_token parses.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    login.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip auth.json verification (just run the CLI).",
    )
    login.add_argument(
        "--skip-cli",
        action="store_true",
        help="Don't run `codex login`; only verify an existing auth.json.",
    )

    p.set_defaults(func=cmd_codex)


def cmd_codex(args) -> int:
    if args.codex_cmd == "login":
        return _codex_login(skip_cli=args.skip_cli, verify=not args.no_verify)
    return 2


def _codex_login(*, skip_cli: bool, verify: bool) -> int:
    if not skip_cli:
        codex_path = shutil.which("codex")
        if not codex_path:
            print("codex CLI not found on PATH.")
            print()
            print("Step 1 — install the codex CLI:")
            print(f"    {_CODEX_INSTALL_HINT}")
            print("  (or see https://github.com/openai/codex for other options)")
            print()
            print("Step 2 — log in:")
            print("    codex login")
            print()
            print("Step 3 — verify with butterfly:")
            print("    butterfly codex login --skip-cli")
            return 1

        print(f"Running `{codex_path} login` ...")
        print("  (the CLI will open a browser for ChatGPT OAuth)")
        try:
            rc = subprocess.call([codex_path, "login"])
        except OSError as exc:
            print(f"Error: failed to exec codex CLI: {exc}", file=sys.stderr)
            return 1
        if rc != 0:
            print(f"codex login exited with status {rc}.", file=sys.stderr)
            return rc

    if not verify:
        print("Skipping verification (--no-verify).")
        return 0

    return _verify_codex_auth()


def _verify_codex_auth() -> int:
    path = _CODEX_AUTH_PATH
    if not path.exists():
        print(f"Error: {path} not found after login.", file=sys.stderr)
        print("  Did `codex login` complete successfully?")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: could not parse {path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(
            f"Error: {path} has unexpected shape (expected JSON object, "
            f"got {type(data).__name__}).",
            file=sys.stderr,
        )
        return 1

    tokens = data.get("tokens") or {}
    if not isinstance(tokens, dict):
        print(
            f"Error: {path} has a non-object `tokens` field (got "
            f"{type(tokens).__name__}).",
            file=sys.stderr,
        )
        return 1
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    if not access or not refresh:
        print(
            f"Error: {path} is missing access_token or refresh_token.",
            file=sys.stderr,
        )
        return 1

    # Attempt to surface the account id — same extraction Butterfly will use.
    account_id = ""
    try:
        from butterfly.llm_engine.providers.codex import _extract_account_id
        account_id = _extract_account_id(access, tokens.get("id_token", ""))
    except Exception as exc:  # pragma: no cover — best-effort decorative info
        print(f"Warning: could not extract account id: {exc}", file=sys.stderr)

    print("Codex login verified.")
    print(f"  auth file:  {path}")
    if account_id:
        print(f"  account id: {account_id}")
    print()
    print("You can now run:")
    print("    butterfly chat 'hello'")
    return 0


# ── `butterfly kimi login` ───────────────────────────────────────────────────


def _add_kimi_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "kimi",
        allow_abbrev=False,
        help="Kimi For Coding (Moonshot) provider helpers.",
        description=(
            "Kimi provider helpers.\n\n"
            "Subcommands:\n"
            "  butterfly kimi login       Print the dashboard URL and env-var name\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ksub = p.add_subparsers(dest="kimi_cmd", metavar="COMMAND")
    ksub.required = True

    ksub.add_parser(
        "login",
        allow_abbrev=False,
        help="Print the Kimi dashboard URL and the env var to set.",
        description=(
            "Kimi For Coding uses a static API key — there is no OAuth flow to\n"
            "automate. This command just points you at the dashboard and tells\n"
            "you which env var the provider reads. Copy the key, export it (or\n"
            "add it to your .env), and you're done.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.set_defaults(func=cmd_kimi)


def cmd_kimi(args) -> int:
    if args.kimi_cmd == "login":
        return _kimi_login()
    return 2


def _kimi_login() -> int:
    print("Kimi For Coding — API key setup")
    print()
    print(f"  1. Open {_KIMI_DASHBOARD_URL} and copy your API key.")
    print(f"  2. Export it as {_KIMI_ENV_KEY}, e.g.:")
    print(f"       export {_KIMI_ENV_KEY}=<your-key>")
    print("     or add the same line to your .env file.")
    print()
    print("Done. Sessions using provider='kimi-coding-plan' will pick it up.")
    return 0
