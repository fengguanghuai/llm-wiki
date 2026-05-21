from __future__ import annotations

from datetime import datetime
from pathlib import Path


SKELETON_DIRS: tuple[str, ...] = (
    "raw",
    "raw/articles",
    "raw/papers",
    "raw/notes",
    "raw/refs",
    "wiki",
    "wiki/concepts",
    "wiki/entities",
    "wiki/projects",
    "wiki/syntheses",
    "wiki/playbooks",
    "wiki/inbox",
    "site",
    "outputs/queries",
)

TYPE_DIRS: dict[str, str] = {
    "concept": "concepts",
    "entity": "entities",
    "project": "projects",
    "synthesis": "syntheses",
}


def ensure_skeleton(wiki_root: Path, title: str) -> list[Path]:
    if wiki_root.exists() and not wiki_root.is_dir():
        raise NotADirectoryError(f"wiki root exists but is not a directory: {wiki_root}")

    created: list[Path] = []
    for rel in SKELETON_DIRS:
        path = wiki_root / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    today = datetime.now().date().isoformat()
    for rel, content in _seed_files(title, today).items():
        path = wiki_root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def queryable_files(wiki_root: Path) -> list[Path]:
    wiki = wiki_root / "wiki"
    files: list[Path] = []
    for name in ("index.md", "overview.md", "hot.md", "MEMORY.md"):
        candidate = wiki / name
        if candidate.exists():
            files.append(candidate)
    for folder in ("concepts", "entities", "projects", "syntheses", "playbooks"):
        root = wiki / folder
        if root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def _seed_files(title: str, today: str) -> dict[str, str]:
    safe = title.replace("\n", " ").strip() or "LLM Wiki"
    return {
        "CLAUDE.md": _agent_contract(safe, today, "Claude Code"),
        "AGENTS.md": _agent_contract(safe, today, "AI 代理"),
        "wiki/index.md": _index_template(safe),
        "wiki/MEMORY.md": "# MEMORY\n\n来自 inbox 提升后的长期结论。\n",
        "wiki/log.md": f"# Log\n\n## [{today}] init | 初始化 {safe}\n",
    }


def _agent_contract(title: str, today: str, agent_label: str) -> str:
    return f"""# {title} 知识库

本文件是 {agent_label} 在该 wiki 内的运行约定。

## 范围

- 包含:本地 AI 会话沉淀、可复用决策、精选笔记。
- 不包含:未明确授权导入的私有材料。

## 目录

- `raw/`:只读原始素材。
- `wiki/`:长期沉淀,人工/代理共同维护。
- `wiki/inbox/`:待整理的捕获笔记。
- `site/`:静态产物(预留)。

## 运行规则

1. 操作前先用 `pel` 或 `python3 -m pelib.cli`。
2. 未经授权不要批量导入个人 Vault 或会话归档。
3. `raw/` 保持不可变;长期知识写入 `wiki/`。
4. 先 `capture`,再 `promote` 进入长期页。
5. 不确定结论标注 `--confidence`。
6. 关键动作追加到 `wiki/log.md`。
7. 改正旧结论:手工编辑页面 + `pel correct <page> "改动说明"` 留痕。

## 当前核心页面

- `wiki/index.md`
- `wiki/MEMORY.md`

## 创建日期

- {today}
"""


def _index_template(title: str) -> str:
    return f"""# 索引 - {title}

## 概念(Concepts)
暂无。

## 实体(Entities)
暂无。

## 项目(Projects)
暂无。

## 综合(Syntheses)
暂无。
"""
