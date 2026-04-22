# Personal Execution Library（个人执行库）

一个本地命令行封装层，用于把 AI 代理会话与精选笔记沉淀为可复用的 LLM Wiki。

本仓库包含：

- `pelib/`：`pel` CLI 与本地工作流命令。
- `llmwiki/`：上游 `llm-wiki` 的精简、面向转换的子集。
- `llm-wiki-skill/`：可选的网页预览与 Obsidian 审查工具。

上游来源与边界见 [docs/VENDORED_PROJECTS.md](docs/VENDORED_PROJECTS.md)。

## 功能概览

- 将本地代理会话转换为 Markdown，写入配置的 wiki 根目录。
- 提供 inbox 风格的 capture / promote 知识沉淀流程。
- 检索已沉淀 wiki 页面，支持快速回忆。
- 通过白名单导入指定 Obsidian 文件或目录。
- 可选启动 `llm-wiki-skill` 网页查看器。

## 依赖

- Python 3.9+
- Git
- Node.js / npm（仅在使用网页查看器或 Obsidian 插件时需要）

## AI 代理初始化（推荐）

本项目默认由 AI 代理完成初始化，而不是让用户手工逐条执行。

把仓库 URL 给代理后，代理应先确认以下信息：

1. `wiki_root` 放在哪里（必须先问）。
2. wiki 标题。
3. 是否链接共享技能到 Codex / Claude 目录。

如果用户对路径没有明确偏好，默认使用“代码仓库同级目录”：

- `<repo-parent>/LLM-WIKI Vault`
- 例如仓库在 `/Users/alice/workspace/personal-execution-library`，则默认 wiki 在 `/Users/alice/workspace/LLM-WIKI Vault`

初始化命令：

```bash
python3 -m pelib.cli init --wiki-root "<wiki-root>" --title "<wiki-title>" --link-agents
```

校验命令：

```bash
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
```

`init` 是幂等的：会补齐缺失配置、目录、schema 与 `.pelib/agent-skill`，并尽量保留已有 wiki 内容。

## 手动配置

先复制配置模板：

```bash
cp pelib.example.toml pelib.toml
```

编辑 `pelib.toml`：

```toml
[paths]
wiki_root = "../LLM-WIKI Vault"
llm_wiki_skill_repo = "./llm-wiki-skill"
```

wiki 根目录应包含：

```text
raw/
wiki/
site/
CLAUDE.md
AGENTS.md
```

如果不走 `init`，在执行 `doctor` 前先渲染共享技能：

```bash
python3 -m pelib.cli write-skill
```

## 运行命令

不安装直接运行：

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
```

或安装为可编辑 CLI：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pel status
pel sync --dry-run
```

## 核心工作流

### 同步代理会话

默认启用的适配器：

- `claude_code`
- `codex_cli`
- `copilot-chat`

```bash
pel sync --dry-run
pel sync
```

指定适配器：

```bash
pel sync --adapter codex_cli --dry-run
```

Obsidian 采用显式导入：

```bash
pel obsidian-import "daily-logs/2026-03-25" --dry-run
```

### 沉淀与提升知识

```bash
pel capture "一条可长期复用的结论"
pel inbox
pel promote <inbox-note> --to memory
pel promote-batch --to memory --dry-run
pel query "starship dotfiles"
```

### 审查反馈闭环

```bash
pel feedback "该页面证据链接还不够清晰" --from web --target "wiki/MEMORY.md" --verdict needs-work
pel feedback-inbox
```

### 可选 Web / Obsidian 工具

```bash
pel skill-web-build --install
pel skill-web-serve --port 4175
pel skill-obsidian-build --install
pel skill-obsidian-link "/path/to/your/Obsidian vault"
```

## 共享技能链接

```bash
pel link-agents
```

会创建类似软链接：

- `~/.codex/skills/personal-execution-library -> ./.pelib/agent-skill`
- `~/.claude/skills/personal-execution-library -> ./.pelib/agent-skill`

长期知识始终保存在 `wiki_root`，不放在代理本地技能目录。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 仓库卫生

不要提交本地 wiki 内容、虚拟环境、生成的 `.pelib/` 产物、`node_modules`、构建输出或个人路径配置。
