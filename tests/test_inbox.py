from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from pelib import inbox, wiki
from pelib.config import Config


def _make_cfg(root: Path) -> Config:
    project = root / "project"
    project.mkdir(parents=True, exist_ok=True)
    return Config(
        project_root=project,
        wiki_root=root / "vault",
        skill_name="llm-wiki",
        default_sync_adapters=("claude_code", "codex_cli"),
    )


class CaptureTests(unittest.TestCase):
    def test_capture_creates_file_with_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            path = inbox.capture(
                cfg, "记住这件事", title=None, tags=["mem"], confidence=0.8
            )
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("记住这件事", text)
            self.assertIn("confidence", text)
            self.assertIn("status: open", text)

    def test_capture_writes_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            inbox.capture(cfg, "thing", title=None, tags=[], confidence=None)
            log_text = (cfg.wiki_root / "wiki" / "log.md").read_text(encoding="utf-8")
            self.assertIn("capture |", log_text)


class PromoteTests(unittest.TestCase):
    def test_promote_to_memory_marks_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            captured = inbox.capture(
                cfg, "结论 foo bar baz", title="foo-bar", tags=[], confidence=None
            )
            note = inbox.find_matches(cfg, captured.name)[0]
            target, label = inbox.promote(
                cfg,
                note,
                target_type="memory",
                title=None,
                append=False,
                confidence=None,
            )
            self.assertEqual(label, "wiki/MEMORY.md")
            self.assertIn("结论 foo bar baz", target.read_text(encoding="utf-8"))
            updated = inbox.find_matches(cfg, captured.name)[0]
            self.assertEqual(updated.meta.get("status"), "promoted")

    def test_promote_concept_uses_titlecase_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            captured = inbox.capture(
                cfg,
                "starship 的配置约定",
                title="starship dotfiles",
                tags=[],
                confidence=None,
            )
            note = inbox.find_matches(cfg, captured.name)[0]
            target, label = inbox.promote(
                cfg,
                note,
                target_type="concept",
                title="starship dotfiles",
                append=False,
                confidence=None,
            )
            self.assertEqual(label, "wiki/concepts/StarshipDotfiles.md")
            self.assertTrue(target.exists())

    def test_promote_batch_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            inbox.capture(cfg, "one alpha", title="one", tags=[], confidence=None)
            # ensure different timestamps for filenames
            time.sleep(1.05)
            inbox.capture(cfg, "two beta", title="two", tags=[], confidence=None)
            promoted, errors, _ = inbox.promote_batch(
                cfg,
                target_type="memory",
                append=False,
                limit=0,
                dry_run=True,
                confidence=None,
            )
            self.assertEqual(promoted, 2)
            self.assertEqual(errors, 0)
            memory = (cfg.wiki_root / "wiki" / "MEMORY.md").read_text(encoding="utf-8")
            self.assertNotIn("one alpha", memory)
            self.assertNotIn("two beta", memory)

    def test_promote_refuses_overwrite_without_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            captured = inbox.capture(cfg, "first body", title="duplicate", tags=[], confidence=None)
            note = inbox.find_matches(cfg, captured.name)[0]
            inbox.promote(
                cfg, note, target_type="concept", title="duplicate", append=False, confidence=None
            )
            time.sleep(1.05)
            captured2 = inbox.capture(cfg, "second body", title="duplicate-2", tags=[], confidence=None)
            note2 = inbox.find_matches(cfg, captured2.name)[0]
            with self.assertRaises(FileExistsError):
                inbox.promote(
                    cfg, note2, target_type="concept", title="duplicate", append=False, confidence=None
                )


if __name__ == "__main__":
    unittest.main()
