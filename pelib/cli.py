from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from pelib import __version__
from pelib.config import Config, default_wiki_root, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBSIDIAN_VAULT = Path.home() / "Documents" / "Obsidian Vault"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pel",
        description="Personal Execution Library: one local LLM Wiki for many agents.",
    )
    parser.add_argument("--version", action="version", version=f"pel {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show configured wiki, upstreams, and agent links.")
    sub.add_parser("write-config", help="Create pelib.toml with current defaults.")
    sub.add_parser("write-skill", help="Render the shared agent skill file.")

    p_init = sub.add_parser("init", help="Initialize local config and a wiki root for agent-driven setup.")
    p_init.add_argument(
        "--wiki-root",
        help="Local LLM Wiki root path. Defaults to configured value or <repo-parent>/LLM-WIKI Vault.",
    )
    p_init.add_argument("--title", default="Personal Execution Library", help="Title for a newly scaffolded wiki.")
    p_init.add_argument(
        "--overwrite-config",
        action="store_true",
        help="Rewrite pelib.toml even when it already exists.",
    )
    p_init.add_argument(
        "--link-agents",
        action="store_true",
        help="Symlink the shared skill into supported local agent skill directories.",
    )
    p_init.add_argument("--agents", nargs="+", default=["codex", "claude"], choices=["codex", "claude"])
    p_init.add_argument("--force-link", action="store_true", help="Replace existing non-symlink skill directories.")

    p_link = sub.add_parser("link-agents", help="Symlink the shared skill into agent skill directories.")
    p_link.add_argument("--agents", nargs="+", default=["codex", "claude"], choices=["codex", "claude"])
    p_link.add_argument("--force", action="store_true", help="Replace existing non-symlink skill directories.")

    p_llm = sub.add_parser("llmwiki", help="Run python3 -m llmwiki inside the central wiki root.")
    p_llm.add_argument("args", nargs=argparse.REMAINDER)

    p_sync = sub.add_parser("sync", help="Run safe llmwiki sync against the central wiki root.")
    p_sync.add_argument("--all", action="store_true", help="Run all available upstream adapters, including Obsidian.")
    p_sync.add_argument("--dry-run", action="store_true", help="Show what would be converted without writing.")
    p_sync.add_argument("--adapter", nargs="+", help="Explicit adapter list to run.")
    sub.add_parser("doctor", help="Check for common setup problems.")

    p_capture = sub.add_parser("capture", help="Capture a durable conclusion into the central wiki inbox.")
    p_capture.add_argument("text", help="Conclusion, decision, or memory to save.")
    p_capture.add_argument("--title", help="Optional title. Defaults to a slug from the text.")
    p_capture.add_argument("--tag", action="append", default=[], help="Tag to add; can be repeated.")
    p_capture.add_argument("--confidence", type=float, help="Optional confidence score in [0.0, 1.0].")

    p_inbox = sub.add_parser("inbox", help="List open captured notes in the central wiki inbox.")
    p_inbox.add_argument("--all", action="store_true", help="Show promoted/closed notes too.")

    p_promote = sub.add_parser("promote", help="Promote one inbox note into durable wiki memory or a page.")
    p_promote.add_argument("note", help="Inbox filename, path, or unique substring.")
    p_promote.add_argument(
        "--to",
        choices=["memory", "concept", "entity", "project", "synthesis"],
        default="memory",
        help="Promotion target type. Default: memory.",
    )
    p_promote.add_argument("--title", help="Title for the promoted wiki page or memory section.")
    p_promote.add_argument("--append", action="store_true", help="Append to an existing target page instead of refusing.")
    p_promote.add_argument("--confidence", type=float, help="Override confidence score in [0.0, 1.0].")

    p_promote_batch = sub.add_parser("promote-batch", help="Promote multiple open inbox notes in one run.")
    p_promote_batch.add_argument(
        "--to",
        choices=["memory", "concept", "entity", "project", "synthesis"],
        default="memory",
        help="Promotion target type. Default: memory.",
    )
    p_promote_batch.add_argument("--append", action="store_true", help="Append to an existing target page instead of refusing.")
    p_promote_batch.add_argument("--limit", type=int, default=0, help="Maximum open notes to promote. 0 means no limit.")
    p_promote_batch.add_argument("--dry-run", action="store_true", help="Preview promotions without writing files.")
    p_promote_batch.add_argument("--confidence", type=float, help="Override confidence score in [0.0, 1.0].")

    p_query = sub.add_parser(
        "query",
        help="Search key wiki files and major page folders for relevant matches.",
    )
    p_query.add_argument("text", help="Search text.")
    p_query.add_argument("--limit", type=int, default=12, help="Maximum number of candidate files to show.")

    p_obsidian_import = sub.add_parser(
        "obsidian-import",
        help="Import only selected Obsidian files/folders (whitelist) via the obsidian adapter.",
    )
    p_obsidian_import.add_argument(
        "sources",
        nargs="+",
        help="Whitelist source paths (.md files or folders). Relative paths are resolved under --vault-root.",
    )
    p_obsidian_import.add_argument(
        "--vault-root",
        default=str(DEFAULT_OBSIDIAN_VAULT),
        help=f"Obsidian vault root for resolving relative sources. Default: {DEFAULT_OBSIDIAN_VAULT}",
    )
    p_obsidian_import.add_argument("--min-chars", type=int, default=50, help="Minimum markdown file size in bytes.")
    p_obsidian_import.add_argument("--force", action="store_true", help="Ignore state and reconvert selected files.")
    p_obsidian_import.add_argument("--dry-run", action="store_true", help="Preview conversion without writing output.")

    p_feedback = sub.add_parser("feedback", help="Capture web/Obsidian audit feedback into wiki/feedback.")
    p_feedback.add_argument("text", help="Feedback summary text.")
    p_feedback.add_argument("--title", help="Optional title. Defaults to a slug from the summary.")
    p_feedback.add_argument("--from", dest="source_channel", choices=["web", "obsidian"], default="web")
    p_feedback.add_argument("--target", help="Optional page, project, or topic this feedback refers to.")
    p_feedback.add_argument(
        "--verdict",
        choices=["approve", "needs-work", "question", "blocked", "info"],
        default="info",
        help="Audit verdict label.",
    )
    p_feedback.add_argument("--tag", action="append", default=[], help="Tag to add; can be repeated.")

    p_feedback_inbox = sub.add_parser("feedback-inbox", help="List captured audit feedback notes.")
    p_feedback_inbox.add_argument("--all", action="store_true", help="Show resolved/dismissed notes too.")

    p_skill_web_build = sub.add_parser(
        "skill-web-build",
        help="Build llm-wiki-skill web viewer assets (audit-shared + web client).",
    )
    p_skill_web_build.add_argument(
        "--install",
        action="store_true",
        help="Run npm install in required packages before build.",
    )

    p_skill_web_serve = sub.add_parser(
        "skill-web-serve",
        help="Serve llm-wiki-skill web viewer against the central wiki.",
    )
    p_skill_web_serve.add_argument("--wiki", help="Wiki root passed to the web server. Default: configured wiki_root.")
    p_skill_web_serve.add_argument("--port", default="4175", help="Web viewer port. Default: 4175.")
    p_skill_web_serve.add_argument(
        "--install",
        action="store_true",
        help="Run npm install in required packages before build/start.",
    )

    p_skill_obsidian_build = sub.add_parser(
        "skill-obsidian-build",
        help="Build llm-wiki-skill Obsidian audit plugin (includes audit-shared build).",
    )
    p_skill_obsidian_build.add_argument(
        "--install",
        action="store_true",
        help="Run npm install in required packages before build.",
    )

    p_skill_obsidian_link = sub.add_parser(
        "skill-obsidian-link",
        help="Link built llm-wiki-skill Obsidian audit plugin into an Obsidian vault.",
    )
    p_skill_obsidian_link.add_argument("vault", help="Obsidian vault root path.")
    p_skill_obsidian_link.add_argument(
        "--install",
        action="store_true",
        help="Run npm install/build before link.",
    )

    args = parser.parse_args(argv)
    cfg = load_config(PROJECT_ROOT)

    if args.cmd == "status":
        return cmd_status(cfg)
    if args.cmd == "write-config":
        return cmd_write_config(cfg)
    if args.cmd == "write-skill":
        write_skill(cfg)
        print(f"wrote {cfg.skill_dir / 'SKILL.md'}")
        return 0
    if args.cmd == "init":
        return cmd_init(
            cfg,
            wiki_root_raw=args.wiki_root,
            title=args.title,
            overwrite_config=args.overwrite_config,
            link_agents=args.link_agents,
            agents=args.agents,
            force_link=args.force_link,
        )
    if args.cmd == "link-agents":
        write_skill(cfg)
        return cmd_link_agents(cfg, args.agents, args.force)
    if args.cmd == "llmwiki":
        llm_args = args.args
        if llm_args and llm_args[0] == "--":
            llm_args = llm_args[1:]
        return run_llmwiki(cfg, llm_args)
    if args.cmd == "sync":
        sync_args = ["sync"]
        if args.adapter:
            sync_args.extend(["--adapter", *args.adapter])
        elif not args.all:
            sync_args.extend(["--adapter", *cfg.default_sync_adapters])
        if args.dry_run:
            sync_args.append("--dry-run")
        return run_llmwiki(cfg, sync_args)
    if args.cmd == "doctor":
        return cmd_doctor(cfg)
    if args.cmd == "capture":
        return cmd_capture(cfg, args.text, args.title, args.tag, args.confidence)
    if args.cmd == "inbox":
        return cmd_inbox(cfg, args.all)
    if args.cmd == "promote":
        return cmd_promote(cfg, args.note, args.to, args.title, args.append, args.confidence)
    if args.cmd == "promote-batch":
        return cmd_promote_batch(cfg, args.to, args.append, args.limit, args.dry_run, args.confidence)
    if args.cmd == "query":
        return cmd_query(cfg, args.text, args.limit)
    if args.cmd == "obsidian-import":
        return cmd_obsidian_import(cfg, args.sources, args.vault_root, args.min_chars, args.force, args.dry_run)
    if args.cmd == "feedback":
        return cmd_feedback(cfg, args.text, args.title, args.source_channel, args.target, args.verdict, args.tag)
    if args.cmd == "feedback-inbox":
        return cmd_feedback_inbox(cfg, args.all)
    if args.cmd == "skill-web-build":
        return cmd_skill_web_build(cfg, args.install)
    if args.cmd == "skill-web-serve":
        return cmd_skill_web_serve(cfg, args.wiki, args.port, args.install)
    if args.cmd == "skill-obsidian-build":
        return cmd_skill_obsidian_build(cfg, args.install)
    if args.cmd == "skill-obsidian-link":
        return cmd_skill_obsidian_link(cfg, args.vault, args.install)

    parser.error(f"unknown command: {args.cmd}")
    return 2


def cmd_status(cfg: Config) -> int:
    print(f"project_root:        {cfg.project_root}")
    print(f"wiki_root:           {cfg.wiki_root}")
    print(f"llmwiki_package:     {cfg.project_root / 'llmwiki'}")
    print(f"llm_wiki_skill_repo: {cfg.llm_wiki_skill_repo}")
    print(f"default_adapters:    {', '.join(cfg.default_sync_adapters)}")
    print(f"shared_skill:        {cfg.skill_dir / 'SKILL.md'}")
    print()
    for name, dest in agent_destinations(cfg).items():
        marker = "missing"
        if dest.is_symlink():
            marker = f"symlink -> {os.readlink(dest)}"
        elif dest.exists():
            marker = "exists, not symlink"
        print(f"{name:8} {dest} [{marker}]")
    return 0


def cmd_write_config(cfg: Config) -> int:
    path = cfg.project_root / "pelib.toml"
    if path.exists():
        print(f"exists: {path}")
        return 0
    _write_config_file(cfg, default_wiki_root(cfg.project_root))
    print(f"wrote {path}")
    return 0


def _write_config_file(cfg: Config, wiki_root: Path) -> None:
    content = f"""[paths]
wiki_root = "{_toml_string(wiki_root)}"
llm_wiki_skill_repo = "./llm-wiki-skill"

[skill]
name = "{_toml_string(cfg.skill_name)}"

[sync]
default_adapters = ["claude_code", "codex_cli", "copilot-chat"]
"""
    (cfg.project_root / "pelib.toml").write_text(content, encoding="utf-8")


def _toml_string(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _resolve_user_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def cmd_init(
    cfg: Config,
    *,
    wiki_root_raw: str | None,
    title: str,
    overwrite_config: bool,
    link_agents: bool,
    agents: list[str],
    force_link: bool,
) -> int:
    requested_wiki_root = _resolve_user_path(wiki_root_raw) if wiki_root_raw else cfg.wiki_root
    config_path = cfg.project_root / "pelib.toml"
    if config_path.exists() and not overwrite_config and requested_wiki_root != cfg.wiki_root:
        print(
            f"pelib.toml already exists with wiki_root {cfg.wiki_root}; "
            "rerun with --overwrite-config to replace it.",
            file=sys.stderr,
        )
        return 1

    wiki_root = cfg.wiki_root if config_path.exists() and not overwrite_config else requested_wiki_root
    init_cfg = Config(
        project_root=cfg.project_root,
        wiki_root=wiki_root,
        llm_wiki_skill_repo=cfg.llm_wiki_skill_repo,
        default_sync_adapters=cfg.default_sync_adapters,
        skill_name=cfg.skill_name,
    )

    if config_path.exists() and not overwrite_config:
        print(f"kept existing config: {config_path}")
    else:
        _write_config_file(init_cfg, wiki_root)
        print(f"wrote config: {config_path}")

    try:
        created = _ensure_wiki_skeleton(init_cfg, title)
    except NotADirectoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if created:
        print("created wiki files:")
        for path in created:
            print(f"  {path}")
    else:
        print("wiki skeleton already present")

    write_skill(init_cfg)
    print(f"wrote shared skill: {init_cfg.skill_dir / 'SKILL.md'}")

    if link_agents:
        rc = cmd_link_agents(init_cfg, agents, force_link)
        if rc != 0:
            return rc

    return cmd_doctor(init_cfg)


def _ensure_wiki_skeleton(cfg: Config, title: str) -> list[Path]:
    if cfg.wiki_root.exists() and not cfg.wiki_root.is_dir():
        raise NotADirectoryError(f"wiki root exists but is not a directory: {cfg.wiki_root}")

    created: list[Path] = []
    dirs = [
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
        "wiki/feedback",
        "site",
        "audit",
        "audit/resolved",
        "outputs/queries",
    ]
    for rel in dirs:
        path = cfg.wiki_root / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    today = datetime.now().date().isoformat()
    created.extend(
        _write_missing_files(
            cfg.wiki_root,
            {
                "CLAUDE.md": _wiki_schema_template(title, today, "Claude Code"),
                "AGENTS.md": _wiki_schema_template(title, today, "AI 代理"),
                "wiki/index.md": _wiki_index_template(title),
                "wiki/MEMORY.md": "# MEMORY\n\n这里存放从 inbox 提升后的长期结论。\n",
                "wiki/log.md": f"# Log\n\n## [{today}] init | 初始化 {title}\n",
                "audit/.gitkeep": "",
                "audit/resolved/.gitkeep": "",
                "site/.gitkeep": "",
            },
        )
    )
    return created


def _write_missing_files(root: Path, files: dict[str, str]) -> list[Path]:
    created: list[Path] = []
    for rel, content in files.items():
        path = root / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


def _wiki_schema_template(title: str, today: str, agent_label: str) -> str:
    safe_title = title.replace("\n", " ").strip() or "Personal Execution Library"
    return f"""# {safe_title} 知识库

本文件是 {agent_label} 的运行约定。执行任何 wiki 操作前先阅读，并在结构、范围或约定变化时更新。

## 范围

- 包含：本地 AI 会话、可复用决策、工作流沉淀、精选笔记。
- 不包含：未明确授权导入的私有材料。

## 目录说明

- `raw/`：只读原始素材（转换后的来源数据，不直接改写）。
- `wiki/`：人工与代理共同维护的沉淀知识页。
- `wiki/inbox/`：待整理、待提升的捕获笔记。
- `wiki/feedback/`：待处理的审查反馈。
- `site/`：静态输出或预览产物目录。
- `audit/`：来自 Web/Obsidian 的锚点审计意见。

## 运行规则

1. 优先在集成仓库中使用 `pel` 或 `python3 -m pelib.cli`。
2. 未经用户明确同意，不要批量导入个人 Vault 或会话归档。
3. `raw/` 保持不可变；长期知识写入 `wiki/`。
4. 先 `capture`，再通过 `promote` / `promote-batch` 进入长期页。
5. 不确定结论要标注置信度。
6. 关键动作追加到 `wiki/log.md`。

## 当前核心页面

- `wiki/index.md`
- `wiki/MEMORY.md`

## 待决问题

- 优先导入哪些来源目录？
- 哪些主题应升级为独立的概念页或项目页？

## 创建日期

- {today}
"""


def _wiki_index_template(title: str) -> str:
    safe_title = title.replace("\n", " ").strip() or "Personal Execution Library"
    return f"""# 索引 - {safe_title}

## 概念（Concepts）

暂无概念页面。

## 实体（Entities）

暂无实体页面。

## 项目（Projects）

暂无项目页面。

## 综合（Syntheses）

暂无综合页面。

## 待决问题

- 这个 wiki 现在最应该先沉淀什么？
"""


def cmd_link_agents(cfg: Config, agents: list[str], force: bool) -> int:
    for agent, dest in agent_destinations(cfg).items():
        if agent not in agents:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or not dest.exists():
            if dest.is_symlink():
                dest.unlink()
        elif force:
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        else:
            print(f"skip {agent}: {dest} already exists and is not a symlink")
            continue
        dest.symlink_to(cfg.skill_dir, target_is_directory=True)
        print(f"linked {agent}: {dest} -> {cfg.skill_dir}")
    return 0


def cmd_doctor(cfg: Config) -> int:
    ok = True
    checks = [
        ("wiki root", cfg.wiki_root),
        ("wiki CLAUDE.md", cfg.wiki_root / "CLAUDE.md"),
        ("wiki AGENTS.md", cfg.wiki_root / "AGENTS.md"),
        ("bundled llmwiki", cfg.project_root / "llmwiki"),
        ("shared skill", cfg.skill_dir / "SKILL.md"),
    ]
    for label, path in checks:
        exists = path.exists()
        ok = ok and exists
        print(f"{'ok' if exists else 'missing':7} {label:24} {path}")
    optional = cfg.llm_wiki_skill_repo
    if optional.exists():
        print(f"{'ok':7} {'optional llm-wiki-skill':24} {optional}")
        web = optional / "web"
        plugin = optional / "plugins" / "obsidian-audit"
        print(
            f"{'ok' if web.exists() else 'warn':7} "
            f"{'llm-wiki-skill web':24} "
            f"{web}"
        )
        print(
            f"{'ok' if plugin.exists() else 'warn':7} "
            f"{'llm-wiki-skill plugin':24} "
            f"{plugin}"
        )
    else:
        print(f"{'warn':7} {'optional llm-wiki-skill':24} {optional} (not required at runtime)")
    return 0 if ok else 1


def cmd_capture(cfg: Config, text: str, title: str | None, tags: list[str], confidence: float | None) -> int:
    conf = _normalize_confidence(confidence, "confidence")
    if conf is None and confidence is not None:
        return 1
    inbox = cfg.wiki_root / "wiki" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    slug = _slugify(title or text)[:60] or "note"
    path = inbox / f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    all_tags = ["inbox", "agent-capture", *tags]
    frontmatter_tags = ", ".join(f'"{tag}"' for tag in all_tags)
    confidence_line = f"confidence: {conf:.2f}\n" if conf is not None else ""
    content = f"""---
title: "{title or text[:80].replace('"', "'")}"
type: inbox-note
created: {now.isoformat(timespec="seconds")}
tags: [{frontmatter_tags}]
status: open
{confidence_line}---

# {title or text[:80]}

## Captured Conclusion

{text}

## Next Action

- [ ] Review and promote into `wiki/concepts/`, `wiki/entities/`, `wiki/projects/`, or `wiki/MEMORY.md`.
"""
    path.write_text(content, encoding="utf-8")
    _append_log(cfg, now, f"capture | {path.relative_to(cfg.wiki_root)}")
    print(path)
    return 0


def cmd_inbox(cfg: Config, include_all: bool) -> int:
    notes = _read_inbox_notes(cfg)
    shown = 0
    for note in notes:
        status = note["meta"].get("status", "open")
        if status != "open" and not include_all:
            continue
        shown += 1
        created = note["meta"].get("created", "")
        title = note["meta"].get("title", note["path"].stem)
        rel = note["path"].relative_to(cfg.wiki_root)
        print(f"{shown:2}. [{status}] {created} {rel}")
        print(f"    {title}")
    if shown == 0:
        print("No inbox notes.")
    return 0


def cmd_promote(
    cfg: Config,
    note_selector: str,
    target_type: str,
    title: str | None,
    append: bool,
    confidence_override: float | None,
) -> int:
    conf_override = _normalize_confidence(confidence_override, "confidence")
    if conf_override is None and confidence_override is not None:
        return 1
    note = _select_inbox_note(cfg, note_selector)
    if note is None:
        print(f"no matching inbox note: {note_selector}", file=sys.stderr)
        return 1
    if note["meta"].get("status") != "open":
        print(f"note is not open: {note['path']}", file=sys.stderr)
        return 1

    now = datetime.now()
    note_title = title or note["meta"].get("title") or note["path"].stem
    conclusion = _extract_section(note["body"], "Captured Conclusion").strip()
    if not conclusion:
        conclusion = note["body"].strip()
    if not conclusion:
        print(f"note has no content: {note['path']}", file=sys.stderr)
        return 1
    confidence = conf_override if conf_override is not None else _parse_confidence(note["meta"].get("confidence"))

    if target_type == "memory":
        target = cfg.wiki_root / "wiki" / "MEMORY.md"
        _promote_to_memory(target, note_title, conclusion, note["path"], now, confidence)
        target_label = "wiki/MEMORY.md"
    else:
        target = _target_page(cfg, target_type, note_title)
        if target.exists() and not append:
            print(f"target exists, use --append to add to it: {target}", file=sys.stderr)
            return 1
        _promote_to_page(target, target_type, note_title, conclusion, note["path"], now, append, confidence)
        target_label = str(target.relative_to(cfg.wiki_root))

    _mark_note_promoted(note["path"], target_label, now, confidence)
    _append_log(cfg, now, f"promote | {note['path'].relative_to(cfg.wiki_root)} -> {target_label}")
    print(f"promoted {note['path'].relative_to(cfg.wiki_root)} -> {target_label}")
    return 0


def cmd_promote_batch(
    cfg: Config,
    target_type: str,
    append: bool,
    limit: int,
    dry_run: bool,
    confidence_override: float | None,
) -> int:
    conf_override = _normalize_confidence(confidence_override, "confidence")
    if conf_override is None and confidence_override is not None:
        return 1
    if limit < 0:
        print("limit must be >= 0", file=sys.stderr)
        return 1
    notes = [note for note in _read_inbox_notes(cfg) if note["meta"].get("status", "open") == "open"]
    if not notes:
        print("No open inbox notes.")
        return 0
    if limit > 0:
        notes = notes[:limit]

    now = datetime.now()
    errors = 0
    promoted = 0
    for note in notes:
        rel = note["path"].relative_to(cfg.wiki_root)
        note_title = note["meta"].get("title") or note["path"].stem
        conclusion = _extract_section(note["body"], "Captured Conclusion").strip() or note["body"].strip()
        if not conclusion:
            print(f"skip {rel}: empty note body", file=sys.stderr)
            errors += 1
            continue
        confidence = conf_override if conf_override is not None else _parse_confidence(note["meta"].get("confidence"))

        if target_type == "memory":
            target = cfg.wiki_root / "wiki" / "MEMORY.md"
            target_label = "wiki/MEMORY.md"
            if not dry_run:
                _promote_to_memory(target, note_title, conclusion, note["path"], now, confidence)
        else:
            target = _target_page(cfg, target_type, note_title)
            target_label = str(target.relative_to(cfg.wiki_root))
            if target.exists() and not append:
                print(f"skip {rel}: target exists ({target_label}), rerun with --append", file=sys.stderr)
                errors += 1
                continue
            if not dry_run:
                _promote_to_page(target, target_type, note_title, conclusion, note["path"], now, append, confidence)

        if dry_run:
            print(f"[dry-run] {rel} -> {target_label}")
        else:
            _mark_note_promoted(note["path"], target_label, now, confidence)
            _append_log(cfg, now, f"promote | {rel} -> {target_label}")
            print(f"promoted {rel} -> {target_label}")
        promoted += 1

    summary = "would promote" if dry_run else "promoted"
    print(f"summary: {summary} {promoted}, errors {errors}, total {len(notes)}")
    return 0 if errors == 0 else 1


def cmd_query(cfg: Config, text: str, limit: int) -> int:
    if limit <= 0:
        print("limit must be > 0", file=sys.stderr)
        return 1

    files = _query_files(cfg)
    if not files:
        print("No queryable wiki files found.")
        return 1

    terms = _tokenize_query(text)
    if not terms:
        print("query text produced no searchable terms", file=sys.stderr)
        return 1

    hits: list[tuple[int, Path, str]] = []
    for path in files:
        body = path.read_text(encoding="utf-8", errors="replace")
        score, snippet = _score_file_match(body, terms)
        if score > 0:
            hits.append((score, path, snippet))

    if not hits:
        print("No matches.")
        return 0

    hits.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    print(f"query: {text}")
    for idx, (score, path, snippet) in enumerate(hits[:limit], start=1):
        rel = path.relative_to(cfg.wiki_root)
        print(f"{idx:2}. score={score:2d} {rel}")
        print(f"    {snippet}")
    return 0


def cmd_feedback(
    cfg: Config,
    text: str,
    title: str | None,
    source_channel: str,
    target: str | None,
    verdict: str,
    tags: list[str],
) -> int:
    now = datetime.now()
    feedback_root = cfg.wiki_root / "wiki" / "feedback"
    feedback_root.mkdir(parents=True, exist_ok=True)
    note_title = title or text[:80]
    slug = _slugify(title or text)[:60] or "feedback"
    path = feedback_root / f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    all_tags = ["feedback", "audit", f"source-{source_channel}", f"verdict-{verdict}", *tags]
    frontmatter_tags = ", ".join(f'"{tag}"' for tag in all_tags)
    clean_target = target.replace('"', "'") if target else ""
    target_line = f'target: "{clean_target}"\n' if target else ""
    content = f"""---
title: "{note_title.replace('"', "'")}"
type: audit-feedback
created: {now.isoformat(timespec="seconds")}
source: {source_channel}
verdict: {verdict}
status: open
tags: [{frontmatter_tags}]
{target_line}---

# {note_title}

## Summary

{text}

## Findings

- [ ] Add concrete findings here.

## Suggested Action

- [ ] Decide whether to capture/promote into `wiki/MEMORY.md` or project pages.
"""
    path.write_text(content, encoding="utf-8")
    _append_log(cfg, now, f"feedback | {path.relative_to(cfg.wiki_root)}")
    print(path)
    return 0


def cmd_feedback_inbox(cfg: Config, include_all: bool) -> int:
    notes = _read_feedback_notes(cfg)
    shown = 0
    for note in notes:
        status = note["meta"].get("status", "open")
        if status != "open" and not include_all:
            continue
        shown += 1
        created = note["meta"].get("created", "")
        source = note["meta"].get("source", "")
        verdict = note["meta"].get("verdict", "")
        rel = note["path"].relative_to(cfg.wiki_root)
        title = note["meta"].get("title", note["path"].stem)
        print(f"{shown:2}. [{status}] [{source}/{verdict}] {created} {rel}")
        print(f"    {title}")
    if shown == 0:
        print("No feedback notes.")
    return 0


def cmd_obsidian_import(
    cfg: Config,
    sources: list[str],
    vault_root_raw: str,
    min_chars: int,
    force: bool,
    dry_run: bool,
) -> int:
    if min_chars < 0:
        print("min-chars must be >= 0", file=sys.stderr)
        return 1

    vault_root = Path(os.path.expanduser(vault_root_raw)).resolve()
    if not vault_root.exists() or not vault_root.is_dir():
        print(f"vault root does not exist or is not a directory: {vault_root}", file=sys.stderr)
        return 1

    selected = _collect_obsidian_markdown(sources, vault_root)
    if not selected:
        print("No markdown files matched whitelist sources.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="pel-obsidian-whitelist-") as tmp:
        stage_root = Path(tmp) / "vault"
        copied = _stage_obsidian_whitelist(selected, stage_root, vault_root)
        cfg_file = Path(tmp) / "sessions_config.whitelist.json"
        cfg_data = {
            "adapters": {
                "obsidian": {
                    "vault_paths": [str(stage_root)],
                    "exclude_folders": [
                        ".obsidian",
                        ".trash",
                        "Templates",
                        "_templates",
                        "templates",
                        ".git",
                        "node_modules",
                    ],
                    "min_content_chars": min_chars,
                }
            }
        }
        cfg_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")

        print(f"obsidian-import: selected {len(selected)} files")
        print(f"obsidian-import: staged {copied} files at {stage_root}")
        print(f"obsidian-import: dry-run={str(dry_run).lower()} force={str(force).lower()}")
        return run_llmwiki_convert(cfg, ["obsidian"], cfg_file, dry_run=dry_run, force=force)


def run_llmwiki(cfg: Config, args: list[str]) -> int:
    if not cfg.wiki_root.exists():
        print(f"wiki root does not exist: {cfg.wiki_root}", file=sys.stderr)
        return 1
    llmwiki_pkg = cfg.project_root / "llmwiki"
    if not llmwiki_pkg.exists():
        print(f"bundled llmwiki package does not exist: {llmwiki_pkg}", file=sys.stderr)
        return 1
    shim = (
        "import pathlib, sys\n"
        f"sys.path.insert(0, {str(cfg.project_root)!r})\n"
        "import llmwiki\n"
        "root = pathlib.Path.cwd()\n"
        "llmwiki.REPO_ROOT = root\n"
        "llmwiki.PACKAGE_ROOT = pathlib.Path(llmwiki.__file__).resolve().parent\n"
        "from llmwiki.cli import main\n"
        "raise SystemExit(main(sys.argv[1:]))\n"
    )
    cmd = [sys.executable, "-c", shim, *args]
    print(f"+ cd {cfg.wiki_root}")
    print("+ llmwiki " + " ".join(args))
    return subprocess.call(cmd, cwd=cfg.wiki_root)


def run_llmwiki_convert(
    cfg: Config,
    adapters: list[str],
    config_file: Path,
    *,
    dry_run: bool,
    force: bool,
) -> int:
    if not cfg.wiki_root.exists():
        print(f"wiki root does not exist: {cfg.wiki_root}", file=sys.stderr)
        return 1
    llmwiki_pkg = cfg.project_root / "llmwiki"
    if not llmwiki_pkg.exists():
        print(f"bundled llmwiki package does not exist: {llmwiki_pkg}", file=sys.stderr)
        return 1

    py = (
        "import pathlib, sys\n"
        f"sys.path.insert(0, {str(cfg.project_root)!r})\n"
        "import llmwiki\n"
        f"llmwiki.REPO_ROOT = pathlib.Path({str(cfg.wiki_root)!r})\n"
        "llmwiki.PACKAGE_ROOT = pathlib.Path(llmwiki.__file__).resolve().parent\n"
        "from llmwiki.convert import convert_all\n"
        f"adapters = {adapters!r}\n"
        f"config_file = pathlib.Path({str(config_file)!r})\n"
        f"rc = convert_all(adapters=adapters, config_file=config_file, dry_run={dry_run!r}, force={force!r})\n"
        "raise SystemExit(rc)\n"
    )
    print(f"+ cd {cfg.wiki_root}")
    print(f"+ llmwiki.convert_all(adapters={adapters}, config_file={config_file})")
    return subprocess.call([sys.executable, "-c", py], cwd=cfg.wiki_root)


def cmd_skill_web_build(cfg: Config, install: bool) -> int:
    if _ensure_skill_repo(cfg) != 0:
        return 1
    if _ensure_npm() != 0:
        return 1

    audit_shared = cfg.llm_wiki_skill_repo / "audit-shared"
    web = cfg.llm_wiki_skill_repo / "web"
    if _ensure_dirs_exist(
        [
            ("audit-shared", audit_shared),
            ("web", web),
        ]
    ) != 0:
        return 1

    if install and _run_npm(audit_shared, ["install"]) != 0:
        return 1
    if _run_npm(audit_shared, ["run", "build"]) != 0:
        return 1
    if install and _run_npm(web, ["install"]) != 0:
        return 1
    return _run_npm(web, ["run", "build"])


def cmd_skill_web_serve(cfg: Config, wiki_raw: str | None, port: str, install: bool) -> int:
    if cmd_skill_web_build(cfg, install) != 0:
        return 1

    web = cfg.llm_wiki_skill_repo / "web"
    wiki = Path(os.path.expanduser(wiki_raw)).resolve() if wiki_raw else cfg.wiki_root.resolve()
    if not wiki.exists() or not wiki.is_dir():
        print(f"wiki path does not exist or is not a directory: {wiki}", file=sys.stderr)
        return 1

    args = ["start", "--", "--wiki", str(wiki), "--port", str(port)]
    return _run_npm(web, args)


def cmd_skill_obsidian_build(cfg: Config, install: bool) -> int:
    if _ensure_skill_repo(cfg) != 0:
        return 1
    if _ensure_npm() != 0:
        return 1

    audit_shared = cfg.llm_wiki_skill_repo / "audit-shared"
    plugin = cfg.llm_wiki_skill_repo / "plugins" / "obsidian-audit"
    if _ensure_dirs_exist(
        [
            ("audit-shared", audit_shared),
            ("plugins/obsidian-audit", plugin),
        ]
    ) != 0:
        return 1

    if install and _run_npm(audit_shared, ["install"]) != 0:
        return 1
    if _run_npm(audit_shared, ["run", "build"]) != 0:
        return 1
    if install and _run_npm(plugin, ["install"]) != 0:
        return 1
    return _run_npm(plugin, ["run", "build"])


def cmd_skill_obsidian_link(cfg: Config, vault_raw: str, install: bool) -> int:
    if cmd_skill_obsidian_build(cfg, install) != 0:
        return 1

    plugin = cfg.llm_wiki_skill_repo / "plugins" / "obsidian-audit"
    vault = Path(os.path.expanduser(vault_raw)).resolve()
    if not vault.exists() or not vault.is_dir():
        print(f"vault path does not exist or is not a directory: {vault}", file=sys.stderr)
        return 1

    return _run_npm(plugin, ["run", "link", "--", str(vault)])


def _ensure_skill_repo(cfg: Config) -> int:
    if cfg.llm_wiki_skill_repo.exists():
        return 0
    print(f"llm-wiki-skill repo does not exist: {cfg.llm_wiki_skill_repo}", file=sys.stderr)
    return 1


def _ensure_npm() -> int:
    if shutil.which("npm"):
        return 0
    print("npm not found in PATH", file=sys.stderr)
    return 1


def _ensure_dirs_exist(items: list[tuple[str, Path]]) -> int:
    for label, path in items:
        if not path.exists() or not path.is_dir():
            print(f"missing directory [{label}]: {path}", file=sys.stderr)
            return 1
    return 0


def _run_npm(cwd: Path, args: list[str]) -> int:
    cmd = ["npm", *args]
    print(f"+ cd {cwd}")
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=cwd)


def _append_log(cfg: Config, now: datetime, line: str) -> None:
    log = cfg.wiki_root / "wiki" / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n## [{now.strftime('%Y-%m-%d')}] {line}\n")


def _read_inbox_notes(cfg: Config) -> list[dict]:
    inbox = cfg.wiki_root / "wiki" / "inbox"
    if not inbox.exists():
        return []
    notes = []
    for path in sorted(inbox.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        notes.append({"path": path, "meta": meta, "body": body})
    return notes


def _read_feedback_notes(cfg: Config) -> list[dict]:
    feedback = cfg.wiki_root / "wiki" / "feedback"
    if not feedback.exists():
        return []
    notes = []
    for path in sorted(feedback.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        notes.append({"path": path, "meta": meta, "body": body})
    return notes


def _select_inbox_note(cfg: Config, selector: str) -> dict | None:
    candidate = Path(os.path.expanduser(selector))
    if not candidate.is_absolute():
        candidate = cfg.wiki_root / "wiki" / "inbox" / selector
    if candidate.exists():
        text = candidate.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        return {"path": candidate, "meta": meta, "body": body}

    matches = []
    for note in _read_inbox_notes(cfg):
        rel = str(note["path"].relative_to(cfg.wiki_root))
        title = str(note["meta"].get("title", ""))
        if selector in note["path"].name or selector in rel or selector in title:
            matches.append(note)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print("multiple matching inbox notes:", file=sys.stderr)
        for note in matches:
            print(f"  {note['path'].relative_to(cfg.wiki_root)}", file=sys.stderr)
    return None


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        meta[key.strip()] = value
    return meta, body


def _extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    rest = body[match.end() :]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def _query_files(cfg: Config) -> list[Path]:
    wiki = cfg.wiki_root / "wiki"
    files: list[Path] = []
    for path in [wiki / "index.md", wiki / "overview.md", wiki / "hot.md", wiki / "MEMORY.md"]:
        if path.exists():
            files.append(path)
    for folder in ["concepts", "entities", "projects", "syntheses", "playbooks"]:
        root = wiki / folder
        if root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def _collect_obsidian_markdown(sources: list[str], vault_root: Path) -> list[Path]:
    exclude_folders = {
        ".obsidian",
        ".trash",
        "Templates",
        "_templates",
        "templates",
        ".git",
        "node_modules",
    }
    selected: list[Path] = []
    seen: set[Path] = set()

    for raw in sources:
        candidate = Path(os.path.expanduser(raw))
        if not candidate.is_absolute():
            candidate = vault_root / candidate
        candidate = candidate.resolve()
        try:
            rel_from_vault = candidate.relative_to(vault_root)
        except ValueError:
            rel_from_vault = None
        if rel_from_vault and any(part in exclude_folders for part in rel_from_vault.parts):
            print(f"skip excluded source: {raw}", file=sys.stderr)
            continue
        if not candidate.exists():
            print(f"skip missing source: {raw}", file=sys.stderr)
            continue

        if candidate.is_file():
            if candidate.suffix.lower() != ".md":
                print(f"skip non-markdown file: {candidate}", file=sys.stderr)
                continue
            if candidate not in seen:
                seen.add(candidate)
                selected.append(candidate)
            continue

        if candidate.is_dir():
            for md in sorted(candidate.rglob("*.md")):
                rel = md.relative_to(candidate)
                if any(part in exclude_folders for part in rel.parts):
                    continue
                resolved = md.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                selected.append(resolved)
            continue

        print(f"skip unsupported source type: {candidate}", file=sys.stderr)

    return selected


def _stage_obsidian_whitelist(files: list[Path], stage_root: Path, vault_root: Path) -> int:
    count = 0
    for src in files:
        try:
            rel = src.relative_to(vault_root)
            top = _slugify(rel.parts[0]) if len(rel.parts) > 1 else "vault-root"
        except ValueError:
            rel = Path("external") / src.name
            top = "external"

        # Encode full relative path into the staged filename so files like
        # daily-logs/*/work-log.md do not collide on conversion output.
        flattened = _flatten_markdown_relpath(rel)
        dst = _unique_stage_path(stage_root / top / flattened)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    return count


def _unique_stage_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    idx = 2
    while True:
        candidate = parent / f"{stem}-{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def _flatten_markdown_relpath(rel: Path) -> str:
    parts = []
    for raw in rel.with_suffix("").parts:
        part = _slugify(raw) or "part"
        parts.append(part)
    stem = "--".join(parts) if parts else "note"
    return f"{stem}.md"


def _tokenize_query(text: str) -> list[str]:
    # Keep CJK chunks and latin/digit terms; ignore one-character latin tokens.
    raw = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text.lower())
    return [term for term in raw if len(term) > 1 or re.search(r"[\u4e00-\u9fff]", term)]


def _score_file_match(body: str, terms: list[str]) -> tuple[int, str]:
    lowered = body.lower()
    counts: Counter[str] = Counter()
    for term in terms:
        count = lowered.count(term)
        if count > 0:
            counts[term] = count
    if not counts:
        return 0, ""

    score = len(counts) * 10 + sum(min(count, 5) for count in counts.values())
    return score, _best_snippet(body, list(counts.keys()))


def _best_snippet(body: str, terms: list[str]) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return "(empty file)"
    lowered_terms = [term.lower() for term in terms]
    for line in lines:
        low = line.lower()
        if any(term in low for term in lowered_terms):
            return re.sub(r"\s+", " ", line)[:180]
    return re.sub(r"\s+", " ", lines[0])[:180]


def _promote_to_memory(
    target: Path,
    title: str,
    conclusion: str,
    source: Path,
    now: datetime,
    confidence: float | None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("# MEMORY\n", encoding="utf-8")
    confidence_line = f"- Confidence: {confidence:.2f}\n" if confidence is not None else ""
    with target.open("a", encoding="utf-8") as f:
        f.write(
            f"\n## {title}\n\n"
            f"- Date: {now.date().isoformat()}\n"
            f"- Source: [[{source.stem}]]\n\n"
            f"{confidence_line}"
            f"{conclusion}\n"
        )


def _promote_to_page(
    target: Path,
    target_type: str,
    title: str,
    conclusion: str,
    source: Path,
    now: datetime,
    append: bool,
    confidence: float | None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and append:
        confidence_line = f"Confidence: {confidence:.2f}\n\n" if confidence is not None else ""
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n## Update - {now.date().isoformat()}\n\n"
                f"Source: [[{source.stem}]]\n\n"
                f"{confidence_line}"
                f"{conclusion}\n"
            )
        return

    confidence_line = f"confidence: {confidence:.2f}\n" if confidence is not None else ""
    target.write_text(
        f"""---
title: "{title.replace('"', "'")}"
type: {target_type}
created: {now.date().isoformat()}
updated: {now.date().isoformat()}
sources: ["{source.stem}"]
tags: ["promoted", "agent-capture"]
{confidence_line}---

# {title}

## Summary

{conclusion}

## Connections

- [[{source.stem}]] - captured inbox source.
""",
        encoding="utf-8",
    )


def _target_page(cfg: Config, target_type: str, title: str) -> Path:
    folders = {
        "concept": "concepts",
        "entity": "entities",
        "project": "projects",
        "synthesis": "syntheses",
    }
    folder = folders[target_type]
    slug = _title_slug(title) if target_type in {"concept", "entity"} else _slugify(title)
    return cfg.wiki_root / "wiki" / folder / f"{slug}.md"


def _mark_note_promoted(path: Path, target_label: str, now: datetime, confidence: float | None) -> None:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    meta["status"] = "promoted"
    meta["promoted_at"] = now.isoformat(timespec="seconds")
    meta["promoted_to"] = target_label
    if confidence is not None:
        meta["promoted_confidence"] = f"{confidence:.2f}"
    frontmatter = "\n".join(f"{k}: \"{v}\"" if _needs_quotes(v) else f"{k}: {v}" for k, v in meta.items())
    path.write_text(
        f"---\n{frontmatter}\n---\n{body.rstrip()}\n\n## Promotion\n\n"
        f"- Promoted at: {now.isoformat(timespec='seconds')}\n"
        f"- Promoted to: `{target_label}`\n",
        encoding="utf-8",
    )


def _needs_quotes(value: str) -> bool:
    return any(ch in value for ch in [":", "#", "[", "]", "{", "}", ","]) or value == ""


def _title_slug(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text)
    if not parts:
        return "Untitled"
    if any(re.search(r"[\u4e00-\u9fff]", part) for part in parts):
        return "".join(parts)
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    return text.strip("-")


def _normalize_confidence(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    if value < 0.0 or value > 1.0:
        print(f"{field_name} must be in [0.0, 1.0]", file=sys.stderr)
        return None
    return float(value)


def _parse_confidence(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed < 0.0 or parsed > 1.0:
        return None
    return parsed


def agent_destinations(cfg: Config) -> dict[str, Path]:
    return {
        "codex": Path.home() / ".codex" / "skills" / cfg.skill_name,
        "claude": Path.home() / ".claude" / "skills" / cfg.skill_name,
    }


def write_skill(cfg: Config) -> None:
    cfg.skill_dir.mkdir(parents=True, exist_ok=True)
    skill = f"""---
name: {cfg.skill_name}
description: >-
  当用户希望从共享个人执行库中进行记忆沉淀、导入、检索、更新、审查或复用知识时使用此技能。
  该执行库是由 Codex、Claude Code 等本地代理共享的统一 LLM Wiki。
---

# Personal Execution Library（个人执行库）

这是一个轻量共享技能。不要为当前代理创建新的知识库，统一使用下面的中心 wiki。

## 中心 Wiki

- Wiki 根目录：`{cfg.wiki_root}`
- 原始素材：`{cfg.wiki_root / "raw"}`
- 人工/代理共同维护的知识区：`{cfg.wiki_root / "wiki"}`
- 站点输出：`{cfg.wiki_root / "site"}`
- 代理约定文件：
  - `{cfg.wiki_root / "CLAUDE.md"}`
  - `{cfg.wiki_root / "AGENTS.md"}`

## 工作模型

把中心 wiki 作为长期记忆与执行库：

1. 执行 wiki 操作前先读 `CLAUDE.md` 或 `AGENTS.md`。
2. 回答前先读 `wiki/index.md`、`wiki/overview.md`、`wiki/hot.md`、`wiki/MEMORY.md`。
3. `raw/` 保持不可变，不直接编辑会话转录源文件。
4. 长期知识写入 `wiki/`，不要写回技能目录。
5. 使用 `[[ConceptName]]` 这类 wikilink 建立跨代理关联。
6. 关键操作记录追加到 `wiki/log.md`。

## 常用命令

在集成仓库中执行：

```bash
cd {cfg.project_root}
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "一条可长期复用的结论或决策"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli feedback "这页需要更清晰的证据链接" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
python3 -m pelib.cli feedback-inbox
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "starship dotfiles"
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run
```

## 适用场景

- 用户想知道历史 AI 对话的结论。
- 用户希望导入会话、笔记、文章或决策。
- 用户希望答案基于本地 wiki，而不是通用知识。
- 用户希望不同代理复用同一份沉淀知识。
- 用户要求更新记忆、项目事实或执行约定。
- 用户明确说“记住这个结论”“后面要复用”。

## 工作流建议

- 做同步时优先使用 `pel` 封装命令（若已安装）。
- 深度编辑遵守 `CLAUDE.md` 与 `AGENTS.md` 的规则。
- 长期结论先 `capture`，再用 `inbox` + `promote` 进入 `MEMORY.md`、`concepts/`、`entities/`、`projects/`。
- 不确定结论在 `capture`/`promote` 时加 `--confidence`。
- Web/Obsidian 审查意见通过 `feedback` 采集，再用 `feedback-inbox` 分拣。
- inbox 量大时先 `promote-batch --dry-run` 预演。
- 回答前先 `query`，按相关度定位页面。
- Obsidian 导入优先白名单路径，不要整库盲同步。
- 不确定或猜测性结论不应无标注进入长期页。
- 若 wiki 中不存在该事实，要明确说明并建议补充来源。
- 不要把此 wiki 复制到代理私有目录。
"""
    (cfg.skill_dir / "SKILL.md").write_text(skill, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
