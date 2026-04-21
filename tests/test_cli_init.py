from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pelib.cli import cmd_init
from pelib.config import Config


def _make_cfg(root: Path) -> Config:
    project_root = root / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "llmwiki").mkdir(parents=True, exist_ok=True)
    return Config(
        project_root=project_root,
        wiki_root=root / "default-wiki",
        llm_wiki_skill_repo=project_root / "llm-wiki-skill",
        default_sync_adapters=("claude_code", "codex_cli", "copilot-chat"),
    )


class InitTests(unittest.TestCase):
    def test_init_creates_config_wiki_schema_and_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki_root = root / "central-wiki"

            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_init(
                    cfg,
                    wiki_root_raw=str(wiki_root),
                    title="Team Memory",
                    overwrite_config=False,
                    link_agents=False,
                    agents=["codex", "claude"],
                    force_link=False,
                )

            self.assertEqual(rc, 0)
            config = (cfg.project_root / "pelib.toml").read_text(encoding="utf-8")
            self.assertIn(f'wiki_root = "{wiki_root.resolve()}"', config)
            self.assertTrue((wiki_root / "CLAUDE.md").exists())
            self.assertTrue((wiki_root / "AGENTS.md").exists())
            self.assertTrue((wiki_root / "wiki" / "MEMORY.md").exists())
            skill = (cfg.project_root / ".pelib" / "agent-skill" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(str(wiki_root), skill)

    def test_init_preserves_existing_schema_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki_root = root / "central-wiki"
            wiki_root.mkdir(parents=True)
            (wiki_root / "AGENTS.md").write_text("# Existing rules\n", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                rc = cmd_init(
                    cfg,
                    wiki_root_raw=str(wiki_root),
                    title="Team Memory",
                    overwrite_config=False,
                    link_agents=False,
                    agents=["codex"],
                    force_link=False,
                )

            self.assertEqual(rc, 0)
            self.assertEqual((wiki_root / "AGENTS.md").read_text(encoding="utf-8"), "# Existing rules\n")
            self.assertTrue((wiki_root / "CLAUDE.md").exists())

    def test_init_refuses_mismatched_existing_config_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            configured = root / "configured-wiki"
            requested = root / "requested-wiki"
            (cfg.project_root / "pelib.toml").write_text(
                f'[paths]\nwiki_root = "{configured}"\n',
                encoding="utf-8",
            )
            cfg = Config(
                project_root=cfg.project_root,
                wiki_root=configured,
                llm_wiki_skill_repo=cfg.llm_wiki_skill_repo,
                default_sync_adapters=cfg.default_sync_adapters,
            )

            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = cmd_init(
                    cfg,
                    wiki_root_raw=str(requested),
                    title="Team Memory",
                    overwrite_config=False,
                    link_agents=False,
                    agents=["codex"],
                    force_link=False,
                )

            self.assertEqual(rc, 1)
            self.assertIn("--overwrite-config", err.getvalue())
            self.assertFalse(requested.exists())


if __name__ == "__main__":
    unittest.main()
