from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pelib import __version__
from pelib.config import Config, DEFAULT_UPSTREAM_ROOT, DEFAULT_WIKI_ROOT, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    p_link = sub.add_parser("link-agents", help="Symlink the shared skill into agent skill directories.")
    p_link.add_argument("--agents", nargs="+", default=["codex", "claude"], choices=["codex", "claude"])
    p_link.add_argument("--force", action="store_true", help="Replace existing non-symlink skill directories.")

    p_llm = sub.add_parser("llmwiki", help="Run python3 -m llmwiki inside the central wiki root.")
    p_llm.add_argument("args", nargs=argparse.REMAINDER)

    p_sync = sub.add_parser("sync", help="Run safe llmwiki sync against the central wiki root.")
    p_sync.add_argument("--all", action="store_true", help="Run all available upstream adapters, including Obsidian.")
    p_sync.add_argument("--dry-run", action="store_true", help="Show what would be converted without writing.")
    p_sync.add_argument("--adapter", nargs="+", help="Explicit adapter list to run.")
    sub.add_parser("build", help="Run llmwiki build against the central wiki root.")
    p_serve = sub.add_parser("serve", help="Run llmwiki serve against the central wiki root.")
    p_serve.add_argument("--port", default="8765")

    sub.add_parser("doctor", help="Check for common setup problems.")

    p_capture = sub.add_parser("capture", help="Capture a durable conclusion into the central wiki inbox.")
    p_capture.add_argument("text", help="Conclusion, decision, or memory to save.")
    p_capture.add_argument("--title", help="Optional title. Defaults to a slug from the text.")
    p_capture.add_argument("--tag", action="append", default=[], help="Tag to add; can be repeated.")

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
    if args.cmd == "build":
        return run_llmwiki(cfg, ["build"])
    if args.cmd == "serve":
        return run_llmwiki(cfg, ["serve", "--port", args.port])
    if args.cmd == "doctor":
        return cmd_doctor(cfg)
    if args.cmd == "capture":
        return cmd_capture(cfg, args.text, args.title, args.tag)

    parser.error(f"unknown command: {args.cmd}")
    return 2


def cmd_status(cfg: Config) -> int:
    print(f"project_root:        {cfg.project_root}")
    print(f"wiki_root:           {cfg.wiki_root}")
    print(f"llmwiki_repo:        {cfg.llmwiki_repo}")
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
    content = f"""[paths]
wiki_root = "{DEFAULT_WIKI_ROOT}"
upstream_root = "{DEFAULT_UPSTREAM_ROOT}"

[skill]
name = "personal-execution-library"

[sync]
default_adapters = ["claude_code", "codex_cli", "copilot-chat"]
"""
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")
    return 0


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
        ("wiki package", cfg.wiki_root / "llmwiki"),
        ("upstream llmwiki", cfg.llmwiki_repo),
        ("upstream llm-wiki-skill", cfg.llm_wiki_skill_repo),
        ("shared skill", cfg.skill_dir / "SKILL.md"),
    ]
    for label, path in checks:
        exists = path.exists()
        ok = ok and exists
        print(f"{'ok' if exists else 'missing':7} {label:24} {path}")
    return 0 if ok else 1


def cmd_capture(cfg: Config, text: str, title: str | None, tags: list[str]) -> int:
    inbox = cfg.wiki_root / "wiki" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    slug = _slugify(title or text)[:60] or "note"
    path = inbox / f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    all_tags = ["inbox", "agent-capture", *tags]
    frontmatter_tags = ", ".join(f'"{tag}"' for tag in all_tags)
    content = f"""---
title: "{title or text[:80].replace('"', "'")}"
type: inbox-note
created: {now.isoformat(timespec="seconds")}
tags: [{frontmatter_tags}]
status: open
---

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


def run_llmwiki(cfg: Config, args: list[str]) -> int:
    if not cfg.wiki_root.exists():
        print(f"wiki root does not exist: {cfg.wiki_root}", file=sys.stderr)
        return 1
    if not cfg.llmwiki_repo.exists():
        print(f"llmwiki upstream repo does not exist: {cfg.llmwiki_repo}", file=sys.stderr)
        return 1
    shim = (
        "import pathlib, sys\n"
        f"sys.path.insert(0, {str(cfg.llmwiki_repo)!r})\n"
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


def _append_log(cfg: Config, now: datetime, line: str) -> None:
    log = cfg.wiki_root / "wiki" / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n## [{now.strftime('%Y-%m-%d')}] {line}\n")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    return text.strip("-")


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
  Use this skill when the user asks to remember, ingest, query, update, audit,
  or reuse knowledge from the shared personal execution library. The library is
  one central LLM Wiki shared by Codex, Claude Code, and other local agents.
---

# Personal Execution Library

This is a thin shared skill. Do not create a new knowledge base for this agent.
Use the central wiki below.

## Central Wiki

- Wiki root: `{cfg.wiki_root}`
- Raw sources: `{cfg.wiki_root / "raw"}`
- Human/agent-maintained wiki: `{cfg.wiki_root / "wiki"}`
- Generated site: `{cfg.wiki_root / "site"}`
- Agent schema files:
  - `{cfg.wiki_root / "CLAUDE.md"}`
  - `{cfg.wiki_root / "AGENTS.md"}`

## Operating Model

Use the central wiki as the durable memory and execution library:

1. Read `CLAUDE.md` or `AGENTS.md` at the start of any wiki operation.
2. Read `wiki/index.md`, `wiki/overview.md`, `wiki/hot.md`, and `wiki/MEMORY.md` before answering from the library.
3. Keep `raw/` immutable. Never edit converted session transcripts directly.
4. Write durable knowledge into `wiki/`, not into this skill directory.
5. Use wikilinks like `[[ConceptName]]` for cross-agent references.
6. Append operational notes to `wiki/log.md`.

## Common Commands

Run these from the integration project:

```bash
cd {cfg.project_root}
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "A durable conclusion or decision"
python3 -m pelib.cli build
python3 -m pelib.cli serve
```

## When To Use

- The user asks what past AI conversations concluded.
- The user wants to ingest a conversation, note, article, or decision.
- The user wants an answer grounded in their own local wiki.
- The user wants an agent to reuse knowledge created by another agent.
- The user asks to update memory, project facts, or execution conventions.

## Workflow Hints

- For sync/build/serve, prefer the `pel` wrapper if installed.
- For deep edits, follow the wiki rules in `CLAUDE.md` and `AGENTS.md`.
- If a fact is not in the wiki, say so and suggest what source to ingest.
- Do not copy this wiki into agent-specific folders.
"""
    (cfg.skill_dir / "SKILL.md").write_text(skill, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
