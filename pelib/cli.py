from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pelib import __version__, adapters, correct, inbox, query, skill, sync, wiki
from pelib.config import Config, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(PROJECT_ROOT)
    handler = HANDLERS.get(args.cmd)
    if handler is None:
        parser.error(f"unknown command: {args.cmd}")
        return 2
    return handler(cfg, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pel",
        description="llm-wiki: 个人 LLM 知识库 CLI。",
    )
    parser.add_argument("--version", action="version", version=f"pel {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show configured wiki and agent links.")
    sub.add_parser("doctor", help="Check for common setup problems.")
    sub.add_parser("write-skill", help="Render the shared agent skill file.")

    p_init = sub.add_parser("init", help="Initialize local config and wiki skeleton.")
    p_init.add_argument("--wiki-root", help="Local LLM Wiki root path.")
    p_init.add_argument("--title", default="LLM Wiki")
    p_init.add_argument("--overwrite-config", action="store_true")
    p_init.add_argument("--link-agents", action="store_true")
    p_init.add_argument("--agents", nargs="+", default=list(skill.SUPPORTED_AGENTS), choices=list(skill.SUPPORTED_AGENTS))
    p_init.add_argument("--force-link", action="store_true")

    p_link = sub.add_parser("link-agents", help="Symlink shared skill into agent dirs.")
    p_link.add_argument("--agents", nargs="+", default=list(skill.SUPPORTED_AGENTS), choices=list(skill.SUPPORTED_AGENTS))
    p_link.add_argument("--force", action="store_true")

    p_capture = sub.add_parser("capture", help="Capture a durable conclusion into the inbox.")
    p_capture.add_argument("text")
    p_capture.add_argument("--title")
    p_capture.add_argument("--tag", action="append", default=[])
    p_capture.add_argument("--confidence", type=float)

    p_inbox = sub.add_parser("inbox", help="List inbox notes.")
    p_inbox.add_argument("--all", action="store_true")

    promote_targets = ["memory", "concept", "entity", "project", "synthesis"]
    p_promote = sub.add_parser("promote", help="Promote one inbox note.")
    p_promote.add_argument("note")
    p_promote.add_argument("--to", choices=promote_targets, default="memory")
    p_promote.add_argument("--title")
    p_promote.add_argument("--append", action="store_true")
    p_promote.add_argument("--confidence", type=float)

    p_pb = sub.add_parser("promote-batch", help="Promote multiple open inbox notes.")
    p_pb.add_argument("--to", choices=promote_targets, default="memory")
    p_pb.add_argument("--append", action="store_true")
    p_pb.add_argument("--limit", type=int, default=0)
    p_pb.add_argument("--dry-run", action="store_true")
    p_pb.add_argument("--confidence", type=float)

    p_query = sub.add_parser("query", help="Search wiki for matching pages.")
    p_query.add_argument("text")
    p_query.add_argument("--limit", type=int, default=12)

    p_correct = sub.add_parser("correct", help="Record a correction in wiki/log.md.")
    p_correct.add_argument("page")
    p_correct.add_argument("message")

    p_sync = sub.add_parser("sync", help="Convert AI session sources into raw/sessions/<adapter>/.")
    p_sync.add_argument(
        "--adapter",
        nargs="+",
        help="Adapter names to run. Defaults to configured default_adapters intersected with registered.",
    )
    p_sync.add_argument("--dry-run", action="store_true", help="Discover and convert in memory, don't write files.")

    sub.add_parser("adapters", help="List registered session adapters.")

    return parser


# Handlers --------------------------------------------------------------------

def _cmd_status(cfg: Config, _args: argparse.Namespace) -> int:
    print(f"project_root: {cfg.project_root}")
    print(f"wiki_root:    {cfg.wiki_root}")
    print(f"skill_name:   {cfg.skill_name}")
    print(f"adapters:     {', '.join(cfg.default_sync_adapters)}")
    print(f"shared_skill: {cfg.skill_dir / 'SKILL.md'}")
    print()
    for name, dest in skill.agent_destinations(cfg).items():
        marker = "missing"
        if dest.is_symlink():
            marker = f"symlink -> {os.readlink(dest)}"
        elif dest.exists():
            marker = "exists, not symlink"
        print(f"{name:8} {dest} [{marker}]")
    return 0


def _cmd_doctor(cfg: Config, _args: argparse.Namespace) -> int:
    ok = True
    checks = [
        ("wiki root", cfg.wiki_root),
        ("wiki CLAUDE.md", cfg.wiki_root / "CLAUDE.md"),
        ("wiki AGENTS.md", cfg.wiki_root / "AGENTS.md"),
        ("shared skill", cfg.skill_dir / "SKILL.md"),
    ]
    for label, path in checks:
        exists = path.exists()
        ok = ok and exists
        print(f"{'ok' if exists else 'missing':8} {label:18} {path}")
    return 0 if ok else 1


def _cmd_write_skill(cfg: Config, _args: argparse.Namespace) -> int:
    path = skill.render(cfg)
    print(f"wrote {path}")
    return 0


def _cmd_init(cfg: Config, args: argparse.Namespace) -> int:
    requested = _resolve_path(args.wiki_root) if args.wiki_root else cfg.wiki_root
    config_path = cfg.project_root / "pelib.toml"
    if config_path.exists() and not args.overwrite_config and requested != cfg.wiki_root:
        print(
            f"pelib.toml already exists with wiki_root {cfg.wiki_root}; "
            "rerun with --overwrite-config to replace it.",
            file=sys.stderr,
        )
        return 1

    keep_existing = config_path.exists() and not args.overwrite_config
    final_wiki = cfg.wiki_root if keep_existing else requested
    new_cfg = Config(
        project_root=cfg.project_root,
        wiki_root=final_wiki,
        skill_name=cfg.skill_name,
        default_sync_adapters=cfg.default_sync_adapters,
    )

    if keep_existing:
        print(f"kept existing config: {config_path}")
    else:
        _write_pelib_toml(new_cfg)
        print(f"wrote config: {config_path}")

    try:
        created = wiki.ensure_skeleton(new_cfg.wiki_root, args.title)
    except NotADirectoryError as e:
        print(str(e), file=sys.stderr)
        return 1
    if created:
        print("created wiki files:")
        for p in created:
            print(f"  {p}")
    else:
        print("wiki skeleton already present")

    skill_path = skill.render(new_cfg)
    print(f"wrote shared skill: {skill_path}")

    if args.link_agents:
        rc = _link_agents(new_cfg, args.agents, args.force_link)
        if rc != 0:
            return rc

    return _cmd_doctor(new_cfg, args)


def _cmd_link_agents(cfg: Config, args: argparse.Namespace) -> int:
    skill.render(cfg)
    return _link_agents(cfg, args.agents, args.force)


def _link_agents(cfg: Config, agents: list[str], force: bool) -> int:
    results = skill.link_agents(cfg, agents, force)
    rc = 0
    for agent, dest, action in results:
        if action == "skipped":
            print(f"skip {agent}: {dest} already exists and is not a symlink")
            rc = 1
        else:
            print(f"{action} {agent}: {dest} -> {cfg.skill_dir}")
    return rc


def _cmd_capture(cfg: Config, args: argparse.Namespace) -> int:
    conf = _check_confidence(args.confidence)
    if conf is _INVALID:
        return 1
    path = inbox.capture(
        cfg,
        args.text,
        title=args.title,
        tags=args.tag,
        confidence=conf,
    )
    print(path)
    return 0


def _cmd_inbox(cfg: Config, args: argparse.Namespace) -> int:
    notes = inbox.list_notes(cfg)
    shown = 0
    for note in notes:
        status = note.meta.get("status", "open")
        if status != "open" and not args.all:
            continue
        shown += 1
        created = note.meta.get("created", "")
        title = note.meta.get("title", note.path.stem)
        rel = note.path.relative_to(cfg.wiki_root)
        print(f"{shown:2}. [{status}] {created} {rel}")
        print(f"    {title}")
    if shown == 0:
        print("No inbox notes.")
    return 0


def _cmd_promote(cfg: Config, args: argparse.Namespace) -> int:
    conf = _check_confidence(args.confidence)
    if conf is _INVALID:
        return 1
    matches = inbox.find_matches(cfg, args.note)
    if not matches:
        print(f"no matching inbox note: {args.note}", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print("multiple matching inbox notes:", file=sys.stderr)
        for m in matches:
            print(f"  {m.path.relative_to(cfg.wiki_root)}", file=sys.stderr)
        return 1
    note = matches[0]
    if note.meta.get("status") != "open":
        print(f"note is not open: {note.path}", file=sys.stderr)
        return 1

    try:
        _, label = inbox.promote(
            cfg,
            note,
            target_type=args.to,
            title=args.title,
            append=args.append,
            confidence=conf,
        )
    except (FileExistsError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"promoted {note.path.relative_to(cfg.wiki_root)} -> {label}")
    return 0


def _cmd_promote_batch(cfg: Config, args: argparse.Namespace) -> int:
    if args.limit < 0:
        print("limit must be >= 0", file=sys.stderr)
        return 1
    conf = _check_confidence(args.confidence)
    if conf is _INVALID:
        return 1
    promoted, errors, lines = inbox.promote_batch(
        cfg,
        target_type=args.to,
        append=args.append,
        limit=args.limit,
        dry_run=args.dry_run,
        confidence=conf,
    )
    for line in lines:
        print(line)
    summary = "would promote" if args.dry_run else "promoted"
    print(f"summary: {summary} {promoted}, errors {errors}")
    return 0 if errors == 0 else 1


def _cmd_query(cfg: Config, args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("limit must be > 0", file=sys.stderr)
        return 1
    hits = query.search(cfg, args.text, args.limit)
    if not hits:
        print("No matches.")
        return 0
    print(f"query: {args.text}")
    for idx, hit in enumerate(hits, start=1):
        rel = hit.path.relative_to(cfg.wiki_root)
        print(f"{idx:2}. score={hit.score:2d} {rel}")
        print(f"    {hit.snippet}")
    return 0


def _cmd_correct(cfg: Config, args: argparse.Namespace) -> int:
    try:
        page = correct.record(cfg, args.page, args.message)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    try:
        rel = page.relative_to(cfg.wiki_root)
    except ValueError:
        rel = page
    print(f"correction logged: {rel}")
    return 0


# Utilities -------------------------------------------------------------------

_INVALID: object = object()


def _check_confidence(value: float | None) -> float | None | object:
    if value is None:
        return None
    if 0.0 <= value <= 1.0:
        return float(value)
    print("confidence must be in [0.0, 1.0]", file=sys.stderr)
    return _INVALID


def _resolve_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def _write_pelib_toml(cfg: Config) -> None:
    adapters = ", ".join(f'"{a}"' for a in cfg.default_sync_adapters)
    content = (
        f"[paths]\n"
        f'wiki_root = "{_toml_quote(cfg.wiki_root)}"\n'
        f"\n"
        f"[skill]\n"
        f'name = "{_toml_quote(cfg.skill_name)}"\n'
        f"\n"
        f"[sync]\n"
        f"default_adapters = [{adapters}]\n"
    )
    (cfg.project_root / "pelib.toml").write_text(content, encoding="utf-8")


def _toml_quote(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _cmd_sync(cfg: Config, args: argparse.Namespace) -> int:
    try:
        result = sync.sync(cfg, adapter_names=args.adapter, dry_run=args.dry_run)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 1

    rc = 0
    for name, stats in result.per_adapter.items():
        suffix = " [dry-run]" if args.dry_run else ""
        print(
            f"{name:14}{suffix}  discovered={stats.discovered}  "
            f"converted={stats.converted}  unchanged={stats.unchanged}  "
            f"skipped={stats.skipped}  errored={stats.errored}"
        )
        for err in stats.errors:
            print(f"  ! {err}", file=sys.stderr)
            rc = 1
    return rc


def _cmd_adapters(_cfg: Config, _args: argparse.Namespace) -> int:
    for name in adapters.names():
        cls = adapters.get(name)
        doc = (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else ""
        print(f"{name:14}  {doc}")
    return 0


HANDLERS = {
    "status": _cmd_status,
    "doctor": _cmd_doctor,
    "write-skill": _cmd_write_skill,
    "init": _cmd_init,
    "link-agents": _cmd_link_agents,
    "capture": _cmd_capture,
    "inbox": _cmd_inbox,
    "promote": _cmd_promote,
    "promote-batch": _cmd_promote_batch,
    "query": _cmd_query,
    "correct": _cmd_correct,
    "sync": _cmd_sync,
    "adapters": _cmd_adapters,
}


if __name__ == "__main__":
    raise SystemExit(main())
