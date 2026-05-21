from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ADAPTERS: tuple[str, ...] = ("claude_code", "codex_cli", "gemini_cli")


@dataclass(frozen=True)
class Config:
    project_root: Path
    wiki_root: Path
    skill_name: str
    default_sync_adapters: tuple[str, ...]

    @property
    def skill_dir(self) -> Path:
        return self.project_root / ".pelib" / "agent-skill"


def default_wiki_root(project_root: Path) -> Path:
    return (project_root.parent / "LLM-WIKI Vault").resolve()


def load_config(project_root: Path) -> Config:
    config_path = project_root / "pelib.toml"
    data: dict = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    paths = data.get("paths", {})
    wiki_value = paths.get("wiki_root") or os.environ.get("PEL_WIKI_ROOT")
    wiki_root = _expand(wiki_value, default_wiki_root(project_root), project_root)

    skill = data.get("skill", {})
    skill_name = skill.get("name", "llm-wiki")

    sync = data.get("sync", {})
    adapters = tuple(sync.get("default_adapters", DEFAULT_ADAPTERS))

    return Config(
        project_root=project_root,
        wiki_root=wiki_root,
        skill_name=skill_name,
        default_sync_adapters=adapters,
    )


def _expand(value: str | None, default: Path, base_dir: Path) -> Path:
    if value is None:
        return default.expanduser().resolve()
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()
