from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pelib import correct, wiki
from pelib.config import Config


def _make_cfg(root: Path) -> Config:
    project = root / "project"
    project.mkdir(parents=True, exist_ok=True)
    return Config(
        project_root=project,
        wiki_root=root / "vault",
        skill_name="llm-wiki",
        default_sync_adapters=(),
    )


class CorrectTests(unittest.TestCase):
    def test_correct_appends_log_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            correct.record(cfg, "wiki/MEMORY.md", "fixed typo")
            log_text = (cfg.wiki_root / "wiki" / "log.md").read_text(encoding="utf-8")
            self.assertIn("correct | wiki/MEMORY.md | fixed typo", log_text)

    def test_correct_rejects_missing_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            with self.assertRaises(FileNotFoundError):
                correct.record(cfg, "wiki/nope.md", "x")

    def test_correct_rejects_empty_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            with self.assertRaises(ValueError):
                correct.record(cfg, "wiki/MEMORY.md", "   ")


if __name__ == "__main__":
    unittest.main()
