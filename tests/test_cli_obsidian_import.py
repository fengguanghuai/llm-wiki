from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pelib.cli import (
    _collect_obsidian_markdown,
    _stage_obsidian_whitelist,
    cmd_obsidian_import,
)
from pelib.config import Config


class ObsidianImportTests(unittest.TestCase):
    def test_collect_obsidian_markdown_respects_whitelist_and_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = (Path(tmp) / "vault").resolve()
            (vault / ".obsidian").mkdir(parents=True)
            (vault / "notes").mkdir(parents=True)
            (vault / "notes" / "keep.md").write_text("# keep\n" + ("a" * 80), encoding="utf-8")
            (vault / ".obsidian" / "skip.md").write_text("# skip\n" + ("b" * 80), encoding="utf-8")
            (vault / "notes" / "ignore.txt").write_text("not markdown", encoding="utf-8")

            selected = _collect_obsidian_markdown(
                ["notes", "notes/keep.md", "missing.md", ".obsidian"],
                vault,
            )

            self.assertEqual([p.relative_to(vault).as_posix() for p in selected], ["notes/keep.md"])

    def test_stage_obsidian_whitelist_avoids_same_filename_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            stage = root / "stage"
            a = vault / "daily-logs" / "2026-03-25" / "work-log.md"
            b = vault / "daily-logs" / "2026-03-27" / "work-log.md"
            a.parent.mkdir(parents=True, exist_ok=True)
            b.parent.mkdir(parents=True, exist_ok=True)
            a.write_text("from 03-25", encoding="utf-8")
            b.write_text("from 03-27", encoding="utf-8")

            copied = _stage_obsidian_whitelist([a, b], stage, vault)
            staged = sorted(stage.rglob("*.md"))

            self.assertEqual(copied, 2)
            self.assertEqual(len(staged), 2)
            self.assertNotEqual(staged[0].name, staged[1].name)
            self.assertEqual(sorted(p.read_text(encoding="utf-8") for p in staged), ["from 03-25", "from 03-27"])

    def test_cmd_obsidian_import_passes_dry_run_and_uses_staged_whitelist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            wiki_root = root / "wiki-root"
            llmwiki_repo = root / "llmwiki"
            vault = root / "vault"
            for p in [project_root, wiki_root, llmwiki_repo, vault]:
                p.mkdir(parents=True, exist_ok=True)

            note = vault / "folder" / "note.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text("# note\n" + ("x" * 100), encoding="utf-8")

            cfg = Config(
                project_root=project_root,
                wiki_root=wiki_root,
                llmwiki_repo=llmwiki_repo,
                llm_wiki_skill_repo=root / "skill-upstream",
                default_sync_adapters=("claude_code", "codex_cli", "copilot-chat"),
            )

            call_data: dict[str, object] = {}

            def fake_run_llmwiki_convert(
                _cfg: Config,
                adapters: list[str],
                config_file: Path,
                *,
                dry_run: bool,
                force: bool,
            ) -> int:
                call_data["adapters"] = adapters
                call_data["dry_run"] = dry_run
                call_data["force"] = force
                payload = json.loads(config_file.read_text(encoding="utf-8"))
                call_data["payload"] = payload
                stage_root = Path(payload["adapters"]["obsidian"]["vault_paths"][0])
                call_data["stage_files"] = sorted(p.relative_to(stage_root).as_posix() for p in stage_root.rglob("*.md"))
                return 0

            with patch("pelib.cli.run_llmwiki_convert", side_effect=fake_run_llmwiki_convert):
                rc = cmd_obsidian_import(
                    cfg,
                    ["folder/note.md"],
                    str(vault),
                    min_chars=60,
                    force=False,
                    dry_run=True,
                )

            self.assertEqual(rc, 0)
            self.assertEqual(call_data["adapters"], ["obsidian"])
            self.assertEqual(call_data["dry_run"], True)
            self.assertEqual(call_data["force"], False)
            payload = call_data["payload"]
            self.assertEqual(payload["adapters"]["obsidian"]["min_content_chars"], 60)
            self.assertEqual(len(call_data["stage_files"]), 1)


if __name__ == "__main__":
    unittest.main()
