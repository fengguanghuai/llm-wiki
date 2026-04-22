# AI 代理初始化指南

本仓库设计目标是：由 AI 代理完成初始化，而不是让用户执行冗长手工步骤。
当用户给出本项目 GitHub 地址时，请把本文件当作初始化契约执行。

## 目标

在本地建立一个 Personal Execution Library：

- 一个轻量 Python CLI（`pelib`）
- 一个可长期复用的本地 LLM Wiki 根目录（`wiki_root`）

## 必须先向用户确认的信息

仅在用户未提供时询问：

1. `wiki_root` 存放路径（必须先确认）
2. wiki 标题
3. 是否把共享技能链接到本机 Codex / Claude 目录

路径默认策略（用户不清楚时）：

- 默认放在代码仓库同级目录：`<repo-parent>/LLM-WIKI Vault`
- 示例：仓库在 `/Users/alice/workspace/personal-execution-library`，默认 wiki 在 `/Users/alice/workspace/LLM-WIKI Vault`

不要让用户自己运行初始化命令；拿到必要信息后由代理直接执行。

## 初始化命令

在仓库根目录执行：

```bash
python3 -m pelib.cli init --wiki-root "<wiki-root>" --title "<wiki-title>" --link-agents
```

若 `pelib.toml` 已存在且用户明确要求替换，再加：

```bash
--overwrite-config
```

`init` 是幂等的：会补齐缺失配置、目录、schema 文件和 `.pelib/agent-skill`，并尽量保留既有 wiki 内容。

## 初始化后校验

```bash
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m unittest discover -s tests -v
```

如果用户需要 Node 相关可选能力，再执行：

```bash
python3 -m pelib.cli skill-web-build --install
python3 -m pelib.cli skill-web-serve --port 4175
```

Obsidian 插件：先确认 vault 路径再执行：

```bash
python3 -m pelib.cli skill-obsidian-link "<obsidian-vault>" --install
```

## 安全规则

- 未经用户明确授权，不要批量导入个人 Obsidian、浏览器导出或会话归档。
- 写入前优先 `sync --dry-run`。
- `raw/` 转换后保持不可变。
- 长期结论通过 `capture`、`promote` 或 `wiki/` 下的策展页面沉淀。
- 除非用户明确要求替换，保留现有 `pelib.toml`、`CLAUDE.md`、`AGENTS.md` 与 wiki 页面。

## 常用命令

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli capture "一条长期结论"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli query "搜索关键词"
python3 -m pelib.cli obsidian-import "<显式路径>" --dry-run
```
