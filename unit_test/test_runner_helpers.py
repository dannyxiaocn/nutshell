from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from unit_test._runner import iter_subunit_go_files, repo_root_from
from unit_test_support import iter_unit_dirs, run_unittest_dir


class RunnerHelperTests(unittest.TestCase):
    def test_repo_root_from_finds_project_root(self) -> None:
        root = repo_root_from(Path(__file__))
        self.assertTrue((root / "pyproject.toml").exists())

    def test_iter_subunit_go_files_excludes_root_runner(self) -> None:
        root = repo_root_from(Path(__file__))
        files = {path.relative_to(root).as_posix() for path in iter_subunit_go_files(root)}
        self.assertIn("nutshell/core/unit_test/go.py", files)
        self.assertIn("ui/web/unit_test/go.py", files)
        self.assertNotIn("unit_test/go.py", files)

    def test_iter_unit_dirs_lists_major_unit_roots(self) -> None:
        root = repo_root_from(Path(__file__))
        dirs = {path.relative_to(root).as_posix() for path in iter_unit_dirs()}
        self.assertIn("entity/unit_test", dirs)
        self.assertIn("nutshell/session_engine/unit_test", dirs)
        self.assertIn("ui/cli/unit_test", dirs)

    def test_run_unittest_dir_falls_back_for_non_importable_temp_dir(self) -> None:
        with TemporaryDirectory() as td:
            test_dir = Path(td) / "ad_hoc_tests"
            test_dir.mkdir()
            (test_dir / "test_smoke.py").write_text(
                "import unittest\n\n"
                "class Smoke(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            status = run_unittest_dir(test_dir, verbosity=0)

        self.assertEqual(status, 0)

