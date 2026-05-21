from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pelib import cli


class CliEndToEndTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_init_capture_query_correct_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            wiki_root = Path(tmp) / "vault"

            original = cli.PROJECT_ROOT
            try:
                cli.PROJECT_ROOT = project
                rc, _, err = self._run([
                    "init",
                    "--wiki-root", str(wiki_root),
                    "--title", "Test Vault",
                ])
                self.assertEqual(rc, 0, err)
                self.assertTrue((project / "pelib.toml").exists())
                self.assertTrue((wiki_root / "wiki" / "MEMORY.md").exists())
                self.assertTrue((project / ".pelib" / "agent-skill" / "SKILL.md").exists())

                rc, _, err = self._run(["capture", "记住 starship 主题配置"])
                self.assertEqual(rc, 0, err)
                inbox_files = list((wiki_root / "wiki" / "inbox").glob("*.md"))
                self.assertEqual(len(inbox_files), 1)

                rc, _, err = self._run(["promote", inbox_files[0].name, "--to", "memory"])
                self.assertEqual(rc, 0, err)
                memory = (wiki_root / "wiki" / "MEMORY.md").read_text(encoding="utf-8")
                self.assertIn("starship", memory)

                rc, out, _ = self._run(["query", "starship"])
                self.assertEqual(rc, 0)
                self.assertIn("MEMORY.md", out)

                rc, _, err = self._run(["correct", "wiki/MEMORY.md", "removed stale claim"])
                self.assertEqual(rc, 0, err)
                log_text = (wiki_root / "wiki" / "log.md").read_text(encoding="utf-8")
                self.assertIn("removed stale claim", log_text)
            finally:
                cli.PROJECT_ROOT = original

    def test_doctor_reports_missing_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            original = cli.PROJECT_ROOT
            try:
                cli.PROJECT_ROOT = project
                rc, out, _ = self._run(["doctor"])
                self.assertNotEqual(rc, 0)
                self.assertIn("missing", out)
            finally:
                cli.PROJECT_ROOT = original


if __name__ == "__main__":
    unittest.main()
