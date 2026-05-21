from __future__ import annotations

import shutil
from pathlib import Path

from pelib.config import Config


SUPPORTED_AGENTS: tuple[str, ...] = ("codex", "claude")


def agent_destinations(cfg: Config) -> dict[str, Path]:
    return {
        "codex": Path.home() / ".codex" / "skills" / cfg.skill_name,
        "claude": Path.home() / ".claude" / "skills" / cfg.skill_name,
    }


def render(cfg: Config) -> Path:
    cfg.skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = cfg.skill_dir / "SKILL.md"
    skill_path.write_text(_skill_body(cfg), encoding="utf-8")
    return skill_path


def link_agents(cfg: Config, agents: list[str], force: bool) -> list[tuple[str, Path, str]]:
    results: list[tuple[str, Path, str]] = []
    destinations = agent_destinations(cfg)
    for agent in agents:
        if agent not in destinations:
            continue
        dest = destinations[agent]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            dest.unlink()
            action = "linked"
        elif dest.exists():
            if not force:
                results.append((agent, dest, "skipped"))
                continue
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
            action = "replaced"
        else:
            action = "linked"
        dest.symlink_to(cfg.skill_dir, target_is_directory=True)
        results.append((agent, dest, action))
    return results


def _skill_body(cfg: Config) -> str:
    return f"""---
name: {cfg.skill_name}
description: >-
  当用户希望从共享 llm-wiki 中沉淀、检索、更新或复用知识时使用此技能。
  该知识库由 Codex、Claude Code 等本地代理共享。
---

# llm-wiki(个人知识库)

不要在代理本地复制一份知识库,统一使用下面这个中心 wiki。

## 中心 Wiki

- 根目录:`{cfg.wiki_root}`
- 原始素材:`{cfg.wiki_root / "raw"}`
- 长期沉淀:`{cfg.wiki_root / "wiki"}`
- 站点输出:`{cfg.wiki_root / "site"}`
- 代理约定:
  - `{cfg.wiki_root / "CLAUDE.md"}`
  - `{cfg.wiki_root / "AGENTS.md"}`

## 工作流

1. 任何动作前先读 `CLAUDE.md` / `AGENTS.md`。
2. 回答前先看 `wiki/index.md`、`wiki/MEMORY.md`。
3. `raw/` 不直接编辑。
4. 长期知识写入 `wiki/`。
5. 用 `[[ConceptName]]` 做跨页关联。
6. 关键操作追加到 `wiki/log.md`。
7. 纠错:手工编辑页面 + `pel correct <page> "改动说明"` 留痕。

## 常用命令

```bash
cd {cfg.project_root}
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli capture "一条可复用的结论"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli query "关键词"
python3 -m pelib.cli correct "wiki/MEMORY.md" "修正了 X,因为 Y"
```

## 适用场景

- 回忆历史会话结论。
- 沉淀长期决策、概念、项目事实。
- 多代理(Codex / Claude Code 等)复用同一份知识。
- 用户明确要求"记住这个"。

## 注意

- 不确定的结论用 `--confidence` 标注。
- 回答前先 `query`,定位 wiki 中是否已有相关页。
- wiki 中没有的事实,要明确说"没有依据,建议补充来源"。
- 不要把此 wiki 复制到代理私有目录。
"""
