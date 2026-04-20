from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # Python 3.9/3.10 on macOS.
    tomllib = None


DEFAULT_WIKI_ROOT = Path.home() / "Documents/Obsidian Vault/LLM Wiki"
DEFAULT_UPSTREAM_ROOT = (
    Path.home()
    / "Documents/Codex/2026-04-19-mac-2/workspace/upstreams"
)


@dataclass(frozen=True)
class Config:
    project_root: Path
    wiki_root: Path
    llmwiki_repo: Path
    llm_wiki_skill_repo: Path
    default_sync_adapters: tuple[str, ...]
    skill_name: str = "personal-execution-library"

    @property
    def skill_dir(self) -> Path:
        return self.project_root / "agent-skill"


def load_config(project_root: Path) -> Config:
    config_path = project_root / "pelib.toml"
    data: dict = {}
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        data = tomllib.loads(text) if tomllib else _parse_simple_toml(text)

    paths = data.get("paths", {})
    wiki_root = _expand(paths.get("wiki_root"), DEFAULT_WIKI_ROOT)
    upstream_root = _expand(paths.get("upstream_root"), DEFAULT_UPSTREAM_ROOT)
    llmwiki_repo = _expand(paths.get("llmwiki_repo"), upstream_root / "llm-wiki")
    skill_repo = _expand(
        paths.get("llm_wiki_skill_repo"),
        upstream_root / "llm-wiki-skill",
    )

    skill = data.get("skill", {})
    skill_name = skill.get("name", "personal-execution-library")
    sync = data.get("sync", {})
    default_adapters = tuple(
        sync.get(
            "default_adapters",
            ["claude_code", "codex_cli", "copilot-chat"],
        )
    )

    return Config(
        project_root=project_root,
        wiki_root=wiki_root,
        llmwiki_repo=llmwiki_repo,
        llm_wiki_skill_repo=skill_repo,
        default_sync_adapters=default_adapters,
        skill_name=skill_name,
    )


def _expand(value: str | os.PathLike | None, default: Path) -> Path:
    if value is None:
        return default.expanduser()
    return Path(os.path.expandvars(os.path.expanduser(str(value))))


def _parse_simple_toml(text: str) -> dict:
    """Parse the tiny TOML subset used by pelib.toml.

    This supports section headers and quoted string values. It is deliberately
    small so Python 3.9 can run the wrapper without extra dependencies.
    """
    root: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = root.setdefault(section, {})
            continue
        if "=" not in line or current is None:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = []
            inner = value[1:-1].strip()
            for part in inner.split(","):
                part = part.strip()
                if len(part) >= 2 and part[0] == part[-1] == '"':
                    part = part[1:-1]
                if part:
                    items.append(part)
            current[key] = items  # type: ignore[assignment]
            continue
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        current[key] = value
    return root
