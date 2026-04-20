"""Obsidian Web Clipper intake path (v1.0 · #149).

Scans a configured directory for markdown files dropped by the
Obsidian Web Clipper extension and queues them for wiki ingestion.

Configuration (in ``sessions_config.json``):

  - ``web_clipper.enabled``: bool (default: false)
  - ``web_clipper.watch_dir``: str — path to scan (default: "raw/web")
  - ``web_clipper.extensions``: list (default: [".md"])
  - ``web_clipper.auto_queue``: bool — auto-add to ingest queue (default: true)

Workflow:
  1. User clips an article via Obsidian Web Clipper
  2. Web Clipper saves to the configured watch_dir
  3. ``scan_for_clips()`` finds new files not yet queued
  4. If ``auto_queue`` is true, adds them to ``.llmwiki-queue.json``

The function can be called from the SessionStart hook or from
``/wiki-sync`` to catch newly clipped articles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from llmwiki import REPO_ROOT
from llmwiki.queue import enqueue, peek

DEFAULT_WATCH_DIR = REPO_ROOT / "raw" / "web"


def load_web_clipper_config(config: dict[str, Any]) -> dict[str, Any]:
    """Extract web_clipper config with defaults."""
    wc = config.get("web_clipper", {})
    return {
        "enabled": wc.get("enabled", False),
        "watch_dir": Path(wc.get("watch_dir", str(DEFAULT_WATCH_DIR))).expanduser(),
        "extensions": wc.get("extensions", [".md"]),
        "auto_queue": wc.get("auto_queue", True),
    }


def scan_for_clips(
    *,
    config: Optional[dict[str, Any]] = None,
    queue_file: Optional[Path] = None,
) -> list[str]:
    """Scan the Web Clipper watch directory for new files.

    Returns the list of newly queued relative paths.
    New files are those not already in the pending queue.
    """
    wc = load_web_clipper_config(config or {})

    if not wc["enabled"]:
        return []

    watch_dir: Path = wc["watch_dir"]
    if not watch_dir.is_dir():
        return []

    # Find all matching files
    found: list[str] = []
    for ext in wc["extensions"]:
        for p in sorted(watch_dir.rglob(f"*{ext}")):
            if p.name.startswith("_"):
                continue
            try:
                rel = str(p.relative_to(REPO_ROOT))
            except ValueError:
                rel = str(p)
            found.append(rel)

    if not found:
        return []

    # Check what's already queued
    already_queued = set(peek(queue_file=queue_file))
    new_files = [f for f in found if f not in already_queued]

    if new_files and wc["auto_queue"]:
        enqueue(new_files, queue_file=queue_file)

    return new_files
