"""llmwiki CLI (conversion-focused slim variant).

Usage:
    python3 -m llmwiki <subcommand> [options]

Subcommands:
    init      Scaffold raw/ + wiki/ basics
    sync      Convert session/document sources to markdown
    adapters  List registered adapters
    version   Print version and exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from llmwiki import __version__, REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_adapters


def cmd_version(args: argparse.Namespace) -> int:
    print(f"llmwiki {__version__}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    for name in ("raw/sessions", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses"):
        p = REPO_ROOT / name
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not keep.exists() and not any(p.iterdir()):
            keep.touch()
        print(f"  {p.relative_to(REPO_ROOT)}/")

    seeds = {
        "wiki/index.md": "# Wiki Index\n\n## Overview\n- [Overview](overview.md)\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Syntheses\n",
        "wiki/overview.md": "---\ntitle: \"Overview\"\ntype: synthesis\nsources: []\nlast_updated: \"\"\n---\n\n# Overview\n",
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of operations.\n",
        "wiki/MEMORY.md": "---\ntitle: \"Cross-Session Memory\"\ntype: navigation\nlast_updated: \"\"\n---\n\n# MEMORY\n",
    }
    for rel, content in seeds.items():
        p = REPO_ROOT / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"  seeded {p.relative_to(REPO_ROOT)}")
    return 0


def _adapter_status(name: str, adapter_cls: Any, config: dict) -> tuple[str, str]:
    adapter_cfg = config.get(name, {})
    enabled_in_cfg = None
    if isinstance(adapter_cfg, dict):
        enabled_in_cfg = adapter_cfg.get("enabled", None)
    if enabled_in_cfg is True:
        configured = "explicit"
    elif enabled_in_cfg is False:
        configured = "off"
    else:
        configured = "auto"
    available = adapter_cls.is_available()
    will_fire = "yes" if available and configured != "off" else "no"
    return configured, will_fire


def cmd_adapters(args: argparse.Namespace) -> int:
    import json as _json

    discover_adapters()
    if not REGISTRY:
        print("No adapters registered.")
        return 0

    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    config: dict = {}
    if config_path.is_file():
        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    print("Registered adapters:")
    print(f"  {'name':<16}  {'default':<8}  {'configured':<10}  {'will_fire':<9}  description")
    print(f"  {'-' * 16}  {'-' * 8}  {'-' * 10}  {'-' * 9}  {'-' * 40}")
    for name, adapter_cls in sorted(REGISTRY.items()):
        default_avail = "yes" if adapter_cls.is_available() else "no"
        configured, will_fire = _adapter_status(name, adapter_cls, config)
        desc = adapter_cls.description()
        if len(desc) > 40:
            desc = desc[:37] + "..."
        print(f"  {name:<16}  {default_avail:<8}  {configured:<10}  {will_fire:<9}  {desc}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from llmwiki.convert import convert_all

    return convert_all(
        adapters=args.adapter,
        since=args.since,
        project=args.project,
        include_current=args.include_current,
        force=args.force,
        dry_run=args.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmwiki",
        description="LLM session/document to markdown conversion toolkit.",
    )
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    init = sub.add_parser("init", help="Scaffold raw/ and wiki/ structure")
    init.set_defaults(func=cmd_init)

    sync = sub.add_parser("sync", help="Convert new source sessions/docs to markdown")
    sync.add_argument("--adapter", nargs="*", default=None, help="Adapter(s) to run; default: all available")
    sync.add_argument("--since", type=str, help="Only sessions on or after YYYY-MM-DD")
    sync.add_argument("--project", type=str, help="Substring filter on project slug")
    sync.add_argument("--include-current", action="store_true", help="Don't skip live sessions (<60 min)")
    sync.add_argument("--force", action="store_true", help="Ignore state file, reconvert everything")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument(
        "--download-images", action="store_true",
        help="(reserved) image download pipeline is handled by converter options",
    )
    sync.set_defaults(func=cmd_sync)

    ads = sub.add_parser("adapters", help="List available adapters")
    ads.set_defaults(func=cmd_adapters)

    ver = sub.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
