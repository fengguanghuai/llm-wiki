from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pelib.state import SourceState, State


class StateTests(unittest.TestCase):
    def test_load_missing_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = State.load(root)
            self.assertEqual(len(state), 0)

    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = State.load(root)
            state.set(
                "claude_code:/abs/path.jsonl",
                SourceState(sha1="abc", mtime=123.45, output="raw/sessions/claude_code/x.md"),
            )
            state.save()

            reopened = State.load(root)
            self.assertEqual(len(reopened), 1)
            got = reopened.get("claude_code:/abs/path.jsonl")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got.sha1, "abc")
            self.assertAlmostEqual(got.mtime, 123.45)
            self.assertEqual(got.output, "raw/sessions/claude_code/x.md")

    def test_corrupt_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".pel-state.json").write_text("not json", encoding="utf-8")
            state = State.load(root)
            self.assertEqual(len(state), 0)


if __name__ == "__main__":
    unittest.main()
