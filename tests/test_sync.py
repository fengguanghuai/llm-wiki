from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Iterable

from pelib import adapters, sync, wiki
from pelib.adapters.base import Adapter, ConvertedSession, Source
from pelib.config import Config
from pelib.state import State


class FakeAdapter(Adapter):
    name = "fake"

    def __init__(self, sources_root: Path) -> None:
        self.sources_root = sources_root
        self.convert_calls: list[Path] = []

    def discover(self) -> Iterable[Source]:
        for p in sorted(self.sources_root.glob("*.txt")):
            yield Source(adapter=self.name, path=p)

    def convert(self, source: Source) -> ConvertedSession | None:
        self.convert_calls.append(source.path)
        text = source.path.read_text(encoding="utf-8")
        return ConvertedSession(
            source=source,
            output_relative=f"raw/sessions/fake/{source.path.stem}.md",
            frontmatter={"title": source.path.stem, "type": "session", "adapter": "fake"},
            body=f"# {source.path.stem}\n\n{text}",
        )


def _make_cfg(root: Path) -> Config:
    project = root / "project"
    project.mkdir(parents=True, exist_ok=True)
    return Config(
        project_root=project,
        wiki_root=root / "vault",
        skill_name="llm-wiki",
        default_sync_adapters=("fake",),
    )


class SyncOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_registry = dict(adapters.REGISTRY)
        adapters.REGISTRY.clear()

    def tearDown(self) -> None:
        adapters.REGISTRY.clear()
        adapters.REGISTRY.update(self._saved_registry)

    def _register_fake(self, sources_root: Path) -> None:
        bound = lambda: FakeAdapter(sources_root)
        adapters.REGISTRY["fake"] = bound  # type: ignore[assignment]

    def test_sync_writes_outputs_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            sources_root = root / "sources"
            sources_root.mkdir()
            (sources_root / "a.txt").write_text("alpha", encoding="utf-8")
            (sources_root / "b.txt").write_text("beta", encoding="utf-8")
            self._register_fake(sources_root)

            result = sync.sync(cfg, adapter_names=["fake"], dry_run=False)
            stats = result.per_adapter["fake"]
            self.assertEqual(stats.discovered, 2)
            self.assertEqual(stats.converted, 2)
            self.assertEqual(stats.unchanged, 0)

            self.assertTrue((cfg.wiki_root / "raw" / "sessions" / "fake" / "a.md").exists())
            self.assertTrue((cfg.wiki_root / "raw" / "sessions" / "fake" / "b.md").exists())

            state = State.load(cfg.wiki_root)
            self.assertEqual(len(state), 2)

    def test_sync_is_incremental_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            sources_root = root / "sources"
            sources_root.mkdir()
            (sources_root / "a.txt").write_text("alpha", encoding="utf-8")
            self._register_fake(sources_root)

            sync.sync(cfg, adapter_names=["fake"], dry_run=False)
            second = sync.sync(cfg, adapter_names=["fake"], dry_run=False)
            self.assertEqual(second.per_adapter["fake"].unchanged, 1)
            self.assertEqual(second.per_adapter["fake"].converted, 0)

    def test_sync_picks_up_changed_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            sources_root = root / "sources"
            sources_root.mkdir()
            src = sources_root / "a.txt"
            src.write_text("alpha", encoding="utf-8")
            self._register_fake(sources_root)

            sync.sync(cfg, adapter_names=["fake"], dry_run=False)
            src.write_text("alpha v2", encoding="utf-8")
            second = sync.sync(cfg, adapter_names=["fake"], dry_run=False)
            self.assertEqual(second.per_adapter["fake"].converted, 1)
            content = (cfg.wiki_root / "raw" / "sessions" / "fake" / "a.md").read_text(encoding="utf-8")
            self.assertIn("alpha v2", content)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            sources_root = root / "sources"
            sources_root.mkdir()
            (sources_root / "a.txt").write_text("alpha", encoding="utf-8")
            self._register_fake(sources_root)

            result = sync.sync(cfg, adapter_names=["fake"], dry_run=True)
            self.assertEqual(result.per_adapter["fake"].converted, 1)
            self.assertFalse((cfg.wiki_root / "raw" / "sessions" / "fake").exists())
            self.assertFalse((cfg.wiki_root / ".pel-state.json").exists())

    def test_unknown_adapter_raises_keyerror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = _make_cfg(root)
            wiki.ensure_skeleton(cfg.wiki_root, "Test")
            with self.assertRaises(KeyError):
                sync.sync(cfg, adapter_names=["does_not_exist"], dry_run=True)


if __name__ == "__main__":
    unittest.main()
