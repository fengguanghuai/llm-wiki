---
name: llm-wiki
description: >-
  当用户希望从共享本地 LLM Wiki / 执行库中记忆、导入、检索、更新或复用知识时使用。
---

# Personal Execution Library（个人执行库）

这是共享技能模板。不要创建代理私有知识库；使用已配置的中心 wiki。

## 初始化

本地安装建议：

```bash
python3 -m pelib.cli init --wiki-root "../LLM-WIKI Vault" --title "Personal Execution Library" --link-agents
```

该命令会把可执行技能写入 `.pelib/agent-skill/`，并把代理链接到生成后的副本。
仓库中的 `agent-skill/SKILL.md` 仅作为源模板。

中心 wiki 目录应包含：

- `raw/`：不可变原始素材
- `wiki/`：人工/代理共同维护的长期知识
- `site/`：可选生成输出
- `CLAUDE.md` 与/或 `AGENTS.md`：本地运行约定

## 工作模型

1. wiki 操作前读取 `CLAUDE.md` 或 `AGENTS.md`。
2. 回答前读取 `wiki/index.md`、`wiki/overview.md`、`wiki/hot.md`、`wiki/MEMORY.md`。
3. 保持 `raw/` 不可变，不直接改会话转录源文件。
4. 长期知识写入 `wiki/`，不要写入本技能目录。
5. 使用 `[[ConceptName]]` 这类 wikilink 建立关联。
6. 关键动作追加到 `wiki/log.md`。

## 常用命令

```bash
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "一条可长期复用的结论"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "starship dotfiles"
python3 -m pelib.cli feedback "这页证据链接不够清晰" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
python3 -m pelib.cli feedback-inbox
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run
```

## 工作流建议

- 同步优先使用 `pel`（若已安装）。
- 长期结论先 `capture`，再 `inbox` / `promote`。
- 不确定结论请加 `--confidence`。
- Obsidian 导入使用显式路径，避免整库误导入。
- 若 wiki 中没有该事实，请明确说明并建议补充来源。
