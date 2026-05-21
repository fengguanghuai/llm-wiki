# llm-wiki

一个本地 Python CLI(`pel`),用来把多个 AI 代理(Claude Code、Codex CLI、Gemini CLI 等)的会话和精选笔记沉淀为一份共享的、可长期复用的个人知识库。

整个项目使用 Python 3.11+ 的标准库实现,**零第三方依赖**。

## 为什么不是又一个笔记应用

- 你的"长期记忆"是一堆 Markdown 文件 —— 没有数据库、没有锁定、没有专属应用。
- 多个 AI 代理通过同一份 SKILL.md 软链接到同一个 wiki 根目录,共享同一份"用户记忆"。
- 沉淀流程是显式的(`capture` → `inbox` → `promote`),不是黑盒自动总结。

## 依赖

- Python 3.11+
- Git

仅此而已。无需 Node.js,无需虚拟环境(可选),无需任何 pip 包。

## 快速开始

```bash
# 1. 初始化:配置 + wiki 骨架 + 共享技能软链
python3 -m pelib.cli init --wiki-root "../LLM-WIKI Vault" --title "My LLM Wiki" --link-agents

# 2. 沉淀一条结论
python3 -m pelib.cli capture "一条想长期复用的结论"

# 3. 查看 inbox
python3 -m pelib.cli inbox

# 4. 把 inbox 中的某条提升到长期 MEMORY
python3 -m pelib.cli promote <inbox-note> --to memory

# 5. 检索
python3 -m pelib.cli query "关键词"

# 6. 纠错留痕(你手工编辑页面,这条命令在 log.md 追加一行修订记录)
python3 -m pelib.cli correct "wiki/MEMORY.md" "改了 X,因为 Y"
```

或者安装为可编辑 CLI,直接用 `pel` 短命令:

```bash
pip install -e .
pel status
pel doctor
```

## 工作流总览

```
 capture ──> wiki/inbox/        (短期捕获)
                │
                ▼
            promote ──┬──> wiki/MEMORY.md      (默认目标:简短结论)
                      ├──> wiki/concepts/      (--to concept)
                      ├──> wiki/entities/      (--to entity)
                      ├──> wiki/projects/      (--to project)
                      └──> wiki/syntheses/     (--to synthesis)

 query        ──> 跨上述长期页 + index.md 的全文检索
 correct      ──> 留痕到 wiki/log.md(你自己改页面内容)
```

## Wiki 目录约定

`init` 在 `wiki_root` 下创建并维护:

```
<wiki_root>/
├── CLAUDE.md           # Claude Code 在该 wiki 内的运行约定
├── AGENTS.md           # 通用 AI 代理运行约定
├── raw/                # 只读原始素材(预留给未来的 sync)
├── wiki/
│   ├── index.md
│   ├── MEMORY.md       # 提升后的长期结论
│   ├── log.md          # 操作记录
│   ├── inbox/          # 待整理捕获笔记
│   ├── concepts/
│   ├── entities/
│   ├── projects/
│   ├── syntheses/
│   └── playbooks/
├── site/               # 预留静态产物
└── outputs/queries/    # 预留:查询结果导出
```

## 多代理共享

`init --link-agents` 会创建:

```
~/.codex/skills/llm-wiki   -> <repo>/.pelib/agent-skill
~/.claude/skills/llm-wiki  -> <repo>/.pelib/agent-skill
```

两个代理因此共享同一份 `SKILL.md`,指向同一个 `wiki_root`。

## 命令清单

| 命令 | 作用 |
|---|---|
| `init` | 写 `pelib.toml`、建 wiki 骨架、渲染 SKILL.md、可选软链代理目录 |
| `status` | 显示当前配置和软链状态 |
| `doctor` | 检查 wiki 根目录、wiki 内 CLAUDE.md/AGENTS.md、shared skill 是否存在 |
| `write-skill` | 仅重新渲染 SKILL.md |
| `link-agents` | 软链 SKILL 目录到 `~/.codex/skills` 和 `~/.claude/skills` |
| `capture` | 把一条结论写入 `wiki/inbox/<timestamp>-<slug>.md` |
| `inbox` | 列出 inbox 笔记 |
| `promote` | 把一条 inbox 笔记提升到长期页面 |
| `promote-batch` | 批量提升,支持 `--dry-run` |
| `query` | 在长期页中检索 |
| `correct` | 在 `wiki/log.md` 追加一条纠错记录 |

## 路线图

下一阶段(尚未实现):

- `sync` 命令 + 3 个 adapter(`claude_code` / `codex_cli` / `gemini_cli`),把 CLI 会话转换为 `raw/sessions/` 下的 Markdown。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
