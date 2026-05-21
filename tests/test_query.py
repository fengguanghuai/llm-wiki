from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pelib import inbox, query, wiki
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


class QueryTests(unittest.TestCase):
    def test_query_finds_promoted_memory(self) -> None:
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
            inbox.promote(
                cfg, note, target_type="memory", title=None, append=False, confidence=None
            )
            hits = query.search(cfg, "starship", limit=5)
            self.assertTrue(any("MEMORY.md" in str(h.path) for h in hits))

    def test_query_returns_empty_on_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            hits = query.search(cfg, "nonexistent-xyz-9999", limit=5)
            self.assertEqual(hits, [])

    def test_query_rejects_non_positive_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_cfg(Path(tmp))
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            with self.assertRaises(ValueError):
                query.search(cfg, "x", limit=0)


if __name__ == "__main__":
    unittest.main()
