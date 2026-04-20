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
    if args.cmd == "inbox":
        return cmd_inbox(cfg, args.all)
    if args.cmd == "promote":
        return cmd_promote(cfg, args.note, args.to, args.title, args.append)

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
) -> int:
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

    if target_type == "memory":
        target = cfg.wiki_root / "wiki" / "MEMORY.md"
        _promote_to_memory(target, note_title, conclusion, note["path"], now)
        target_label = "wiki/MEMORY.md"
    else:
        target = _target_page(cfg, target_type, note_title)
        if target.exists() and not append:
            print(f"target exists, use --append to add to it: {target}", file=sys.stderr)
            return 1
        _promote_to_page(target, target_type, note_title, conclusion, note["path"], now, append)
        target_label = str(target.relative_to(cfg.wiki_root))

    _mark_note_promoted(note["path"], target_label, now)
    _append_log(cfg, now, f"promote | {note['path'].relative_to(cfg.wiki_root)} -> {target_label}")
    print(f"promoted {note['path'].relative_to(cfg.wiki_root)} -> {target_label}")
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


def _promote_to_memory(target: Path, title: str, conclusion: str, source: Path, now: datetime) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("# MEMORY\n", encoding="utf-8")
    with target.open("a", encoding="utf-8") as f:
        f.write(
            f"\n## {title}\n\n"
            f"- Date: {now.date().isoformat()}\n"
            f"- Source: [[{source.stem}]]\n\n"
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
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and append:
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n## Update - {now.date().isoformat()}\n\n"
                f"Source: [[{source.stem}]]\n\n"
                f"{conclusion}\n"
            )
        return

    target.write_text(
        f"""---
title: "{title.replace('"', "'")}"
type: {target_type}
created: {now.date().isoformat()}
updated: {now.date().isoformat()}
sources: ["{source.stem}"]
tags: ["promoted", "agent-capture"]
---

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


def _mark_note_promoted(path: Path, target_label: str, now: datetime) -> None:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    meta["status"] = "promoted"
    meta["promoted_at"] = now.isoformat(timespec="seconds")
    meta["promoted_to"] = target_label
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
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli build
python3 -m pelib.cli serve
```

## When To Use

- The user asks what past AI conversations concluded.
- The user wants to ingest a conversation, note, article, or decision.
- The user wants an answer grounded in their own local wiki.
- The user wants an agent to reuse knowledge created by another agent.
- The user asks to update memory, project facts, or execution conventions.
- The user says "remember this", "this is the conclusion", or "use this later".

## Workflow Hints

- For sync/build/serve, prefer the `pel` wrapper if installed.
- For deep edits, follow the wiki rules in `CLAUDE.md` and `AGENTS.md`.
- For durable conclusions, use `capture` first; then use `inbox` and `promote`
  to move reviewed notes into `MEMORY.md`, `concepts/`, `entities/`, or `projects/`.
- Do not promote uncertain or speculative claims without marking uncertainty.
- If a fact is not in the wiki, say so and suggest what source to ingest.
- Do not copy this wiki into agent-specific folders.
"""
    (cfg.skill_dir / "SKILL.md").write_text(skill, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
