from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nutshell.session_engine.session_params import DEFAULT_PARAMS, params_path, read_session_params


class SessionParamsUnitTests(unittest.TestCase):
    def test_malformed_json_falls_back_to_defaults(self) -> None:
        with TemporaryDirectory() as td:
            session_dir = Path(td)
            path = params_path(session_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{bad", encoding="utf-8")

            params = read_session_params(session_dir)

        self.assertEqual(params, DEFAULT_PARAMS)

    def test_default_params_has_expected_keys(self) -> None:
        """DEFAULT_PARAMS has model, provider, thinking, tool_providers."""
        self.assertIn("model", DEFAULT_PARAMS)
        self.assertIn("provider", DEFAULT_PARAMS)
        self.assertIn("thinking", DEFAULT_PARAMS)
        self.assertIn("tool_providers", DEFAULT_PARAMS)

    def test_read_params_merges_with_defaults(self) -> None:
        with TemporaryDirectory() as td:
            session_dir = Path(td)
            path = params_path(session_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"model": "gpt-4"}), encoding="utf-8")

            params = read_session_params(session_dir)

        self.assertEqual(params["model"], "gpt-4")
        self.assertEqual(params["thinking"], DEFAULT_PARAMS["thinking"])
