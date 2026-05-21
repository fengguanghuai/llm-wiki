# AI 代理使用指南

本仓库提供一个本地 CLI(`pel`),用于把多个 AI 代理的会话沉淀为一份共享 wiki。
当用户把本项目地址给到代理时,按以下约定操作。

## 初始化流程

仅在用户未提供时询问:

1. `wiki_root` 放在哪里(必须先确认)。默认推荐:代码仓库同级目录,即 `<repo-parent>/LLM-WIKI Vault`。
2. wiki 标题。
3. 是否把共享技能链接到本机 `~/.codex/skills/` 和 `~/.claude/skills/`;默认链接,除非用户拒绝。

确认后,在仓库根目录运行:

```bash
python3 -m pelib.cli init --wiki-root "<path>" --title "<title>" --link-agents
```

`init` 是幂等的:已有的 `pelib.toml`、wiki 内容、SKILL.md 会被尊重,除非传 `--overwrite-config`。

## 安全规则

- 未经用户明确授权,不要批量导入个人 Obsidian、浏览器导出或会话归档。
- `raw/` 转换后保持不可变;长期知识写入 `wiki/`。
- 不确定结论用 `--confidence 0..1` 标注。
- 关键动作会自动写入 `wiki/log.md`。
- 纠正旧结论:**手工编辑页面**,然后 `pel correct <page> "改动说明"` 留痕。

## 常用命令

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli capture "一条长期结论"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "关键词"
python3 -m pelib.cli correct "wiki/MEMORY.md" "改动说明"
```

## 工作模式

1. 任何 wiki 操作前先读 `<wiki_root>/CLAUDE.md` 或 `<wiki_root>/AGENTS.md`。
2. 回答用户前先 `query` 一遍,看 wiki 是否已有相关页面。
3. 长期结论先 `capture`,再用 `inbox` + `promote` 进入长期页;不要直接写 `wiki/MEMORY.md`,除非用户明确要求。
4. 用 `[[ConceptName]]` 这种 wikilink 在不同页面之间建立关联。
5. 不要把此 wiki 复制到代理私有目录;统一使用中心 `wiki_root`。

## 当 wiki 没有相关结论时

明确告诉用户"wiki 中没有相关条目,这个回答基于通用知识",并可建议用 `capture` 把结论沉淀下来。
