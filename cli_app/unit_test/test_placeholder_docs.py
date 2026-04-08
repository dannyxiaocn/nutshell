from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve()
for candidate in (REPO_ROOT.parent, *REPO_ROOT.parents):
    if (candidate / "pyproject.toml").exists():
        REPO_ROOT = candidate
        break


class CliAppDocsTest(unittest.TestCase):
    def test_readme_marks_directory_as_placeholder(self) -> None:
        text = (REPO_ROOT / "cli_app" / "README.md").read_text(encoding="utf-8")
        self.assertIn("placeholder", text.lower())

    def test_readme_redirects_to_active_cli(self) -> None:
        text = (REPO_ROOT / "cli_app" / "README.md").read_text(encoding="utf-8")
        self.assertIn("ui/cli", text)


if __name__ == "__main__":
    unittest.main()
