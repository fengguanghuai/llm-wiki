from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pelib import wiki


class WikiSkeletonTests(unittest.TestCase):
    def test_ensure_skeleton_creates_dirs_and_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            created = wiki.ensure_skeleton(root, "Test Wiki")
            self.assertTrue((root / "raw").is_dir())
            self.assertTrue((root / "wiki" / "inbox").is_dir())
            self.assertTrue((root / "wiki" / "MEMORY.md").exists())
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertGreater(len(created), 0)

    def test_ensure_skeleton_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            wiki.ensure_skeleton(root, "Test")
            (root / "wiki" / "MEMORY.md").write_text("# CUSTOM\n", encoding="utf-8")
            second = wiki.ensure_skeleton(root, "Test")
            self.assertEqual(second, [])
            self.assertEqual(
                (root / "wiki" / "MEMORY.md").read_text(encoding="utf-8"),
                "# CUSTOM\n",
            )

    def test_rejects_non_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "block"
            blocker.write_text("not a dir", encoding="utf-8")
            with self.assertRaises(NotADirectoryError):
                wiki.ensure_skeleton(blocker, "X")


if __name__ == "__main__":
    unittest.main()
