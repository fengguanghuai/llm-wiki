from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pelib.cli import cmd_promote, cmd_promote_batch, cmd_query
from pelib.config import Config


def _make_cfg(root: Path) -> Config:
    project_root = root / "project"
    wiki_root = root / "wiki-root"
    for p in [project_root, wiki_root]:
        p.mkdir(parents=True, exist_ok=True)
    return Config(
        project_root=project_root,
        wiki_root=wiki_root,
        llm_wiki_skill_repo=root / "llm-wiki-skill",
        default_sync_adapters=("claude_code", "codex_cli", "copilot-chat"),
    )


def _write_inbox_note(path: Path, title: str, body: str, confidence: float | None = None) -> None:
    confidence_line = f"confidence: {confidence:.2f}\n" if confidence is not None else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            f"title: \"{title}\"\n"
            "type: inbox-note\n"
            "created: 2026-04-20T00:00:00\n"
            "status: open\n"
            f"{confidence_line}"
            "---\n\n"
            f"# {title}\n\n"
            "## Captured Conclusion\n\n"
            f"{body}\n"
        ),
        encoding="utf-8",
    )


class QueryAndPromoteBatchTests(unittest.TestCase):
    def test_query_prefers_files_matching_more_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki = cfg.wiki_root / "wiki"
            wiki.mkdir(parents=True, exist_ok=True)
            (wiki / "index.md").write_text("alpha only", encoding="utf-8")
            (wiki / "MEMORY.md").write_text("alpha beta both", encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_query(cfg, "alpha beta", limit=5)

            self.assertEqual(rc, 0)
            lines = [line for line in out.getvalue().splitlines() if line.strip()]
            self.assertIn("query: alpha beta", lines[0])
            # MEMORY should rank before index because it matches 2 unique terms.
            joined = "\n".join(lines)
            self.assertLess(joined.find("wiki/MEMORY.md"), joined.find("wiki/index.md"))

    def test_promote_batch_dry_run_does_not_mutate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            inbox = cfg.wiki_root / "wiki" / "inbox"
            note = inbox / "20260420-000000-sample.md"
            _write_inbox_note(note, "Sample", "Dry run body", confidence=0.8)

            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_promote_batch(
                    cfg,
                    target_type="memory",
                    append=False,
                    limit=0,
                    dry_run=True,
                    confidence_override=None,
                )

            self.assertEqual(rc, 0)
            self.assertIn("would promote 1", out.getvalue())
            self.assertFalse((cfg.wiki_root / "wiki" / "MEMORY.md").exists())
            text = note.read_text(encoding="utf-8")
            self.assertIn("status: open", text)
            self.assertNotIn("Promoted at:", text)

    def test_promote_batch_conflict_without_append_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            inbox = cfg.wiki_root / "wiki" / "inbox"
            note = inbox / "20260420-000000-starship.md"
            _write_inbox_note(note, "Starship Prompt", "Keep defaults")

            target = cfg.wiki_root / "wiki" / "concepts" / "StarshipPrompt.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# existing", encoding="utf-8")

            err = io.StringIO()
            with redirect_stderr(err):
                rc = cmd_promote_batch(
                    cfg,
                    target_type="concept",
                    append=False,
                    limit=0,
                    dry_run=False,
                    confidence_override=None,
                )

            self.assertEqual(rc, 1)
            self.assertIn("target exists", err.getvalue())
            self.assertIn("status: open", note.read_text(encoding="utf-8"))

    def test_promote_uses_confidence_from_note_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            note = cfg.wiki_root / "wiki" / "inbox" / "20260420-000000-confidence.md"
            _write_inbox_note(note, "Confidence Note", "Strong signal", confidence=0.65)

            rc = cmd_promote(
                cfg,
                note_selector="20260420-000000-confidence.md",
                target_type="memory",
                title=None,
                append=False,
                confidence_override=None,
            )

            self.assertEqual(rc, 0)
            memory = (cfg.wiki_root / "wiki" / "MEMORY.md").read_text(encoding="utf-8")
            self.assertIn("Confidence: 0.65", memory)
            updated_note = note.read_text(encoding="utf-8")
            self.assertIn("promoted_confidence: 0.65", updated_note)


if __name__ == "__main__":
    unittest.main()
