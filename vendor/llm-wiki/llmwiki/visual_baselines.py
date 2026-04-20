"""Visual regression baselines via SHA-256 hashing (v1.2.0 · #113).

Approach
--------
Byte-identical comparison of PNG screenshots against a committed JSON
file of ``{filename: sha256}`` pairs. **Stdlib only** — no Pillow,
no image-diff libraries.

Why hashing + not perceptual diff?
- llmwiki's "approved UI surfaces" are the 6 prototype states (#114) +
  the home / session / projects pages. They render from deterministic
  CSS + fixed demo data — same browser + same viewport = pixel-identical
  screenshots. A hash change means something *did* change.
- Pillow / pixelmatch would add a runtime dependency. Rule of the
  project is stdlib-only. Hash compare is harsher (no tolerance) but
  demands explicit baseline updates, which is actually what we want —
  every visual change should be reviewed.

Workflow
--------
1. Run the E2E screenshot suite locally: ``pytest tests/e2e/`` with
   ``LLMWIKI_E2E_SCREENSHOT_DIR=tests/e2e/screenshots``. That produces
   PNGs per breakpoint × theme.
2. Review the diffs visually.
3. If they're intentional, refresh the baselines:
   ``scripts/update-visual-baselines.sh``
4. Commit ``tests/e2e/visual_baselines/baselines.json``.
5. On CI, the visual-regression test hashes new screenshots and
   compares against the committed JSON. Any drift → test fails with a
   clear diff listing which files changed.

Public API
----------
- :func:`hash_png` — SHA-256 of a PNG file
- :func:`load_baselines` / :func:`save_baselines` — JSON round-trip
- :func:`generate_baselines` — hash every PNG in a directory
- :func:`compare_against_baselines` — return per-file status dict
- :data:`BaselineStatus` — per-file verdict enum-like literal

Design notes
------------
- **Baseline file is JSON, not binary.** Diffs are reviewable in PRs
  without binary-diff hosting.
- **Relative paths only.** Baselines key by filename so the repo is
  portable across checkouts.
- **Missing baseline ≠ test failure.** First-run-of-a-new-surface
  reports `"new"`, not `"drift"`. The workflow expects the maintainer
  to regenerate after reviewing.
- **Stale baselines ARE a failure.** A baseline without a matching
  screenshot means the surface was removed — fail so the maintainer
  decides to keep or prune the baseline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Literal, Optional, TypedDict

# ─── Constants ─────────────────────────────────────────────────────────

# Literal status a single file can report on a baseline comparison.
BaselineStatus = Literal["match", "drift", "new", "missing"]

# Default location for the committed baseline manifest.
DEFAULT_BASELINES_FILENAME = "baselines.json"


# ─── Core ──────────────────────────────────────────────────────────────


class BaselineEntry(TypedDict):
    """One row in ``baselines.json``."""

    sha256: str
    size: int  # bytes — nice for change-impact review in PRs


def hash_png(path: Path) -> str:
    """Return the SHA-256 hex digest of ``path``.

    Reads in 64 KB chunks so we don't OOM on the biggest screenshots.
    Raises ``FileNotFoundError`` when the path is missing (callers get a
    precise error instead of an empty digest).
    """
    if not path.is_file():
        raise FileNotFoundError(f"screenshot does not exist: {path}")
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _png_entry(path: Path) -> BaselineEntry:
    """Build a BaselineEntry for ``path`` (stat + hash)."""
    return {"sha256": hash_png(path), "size": path.stat().st_size}


# ─── Baseline I/O ──────────────────────────────────────────────────────


def load_baselines(path: Path) -> dict[str, BaselineEntry]:
    """Read the baseline JSON manifest. Missing / unreadable files
    return an empty dict so CI on a fresh branch doesn't crash — it
    just reports every screenshot as ``"new"``."""
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}

    # Accept both the full {"sha256": …, "size": …} shape and the
    # backwards-compatible {"<filename>": "<sha256>"} legacy shape.
    out: dict[str, BaselineEntry] = {}
    for name, value in raw.items():
        if isinstance(value, dict) and "sha256" in value:
            out[name] = {
                "sha256": str(value["sha256"]),
                "size": int(value.get("size", 0)),
            }
        elif isinstance(value, str):
            out[name] = {"sha256": value, "size": 0}
    return out


def save_baselines(
    baselines: dict[str, BaselineEntry],
    path: Path,
) -> Path:
    """Write the baseline manifest as indented JSON sorted by filename
    so PR diffs are small and reviewable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = {
        name: {"sha256": entry["sha256"], "size": entry["size"]}
        for name, entry in sorted(baselines.items())
    }
    path.write_text(
        json.dumps(serialisable, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


# ─── Generation + comparison ───────────────────────────────────────────


def _iter_png_files(
    screenshots_dir: Path,
    *,
    extensions: Iterable[str] = (".png",),
) -> Iterable[Path]:
    """Walk ``screenshots_dir`` yielding every file with a matching
    extension, sorted so hash output is deterministic across runs."""
    if not screenshots_dir.is_dir():
        return []
    exts = {e.lower() for e in extensions}
    return sorted(
        p for p in screenshots_dir.rglob("*") if p.suffix.lower() in exts
    )


def generate_baselines(
    screenshots_dir: Path,
    baselines_path: Optional[Path] = None,
) -> dict[str, BaselineEntry]:
    """Hash every PNG under ``screenshots_dir`` and (optionally) write
    the manifest.

    ``screenshots_dir`` keys are **relative paths** — ``home-phone-
    dark.png`` or ``sub/dir/article.png`` — so the baseline file moves
    cleanly between clones.
    """
    base = screenshots_dir.resolve()
    baselines: dict[str, BaselineEntry] = {}
    for path in _iter_png_files(base):
        rel = str(path.resolve().relative_to(base)).replace("\\", "/")
        baselines[rel] = _png_entry(path)
    if baselines_path is not None:
        save_baselines(baselines, baselines_path)
    return baselines


class ComparisonResult(TypedDict):
    """Aggregate output of :func:`compare_against_baselines`."""

    match: list[str]     # screenshots matching their baseline
    drift: list[str]     # screenshots whose hash changed
    new: list[str]       # screenshots without a baseline entry
    missing: list[str]   # baseline entries without a matching screenshot


def compare_against_baselines(
    screenshots_dir: Path,
    baselines_path: Path,
) -> ComparisonResult:
    """Hash every screenshot under ``screenshots_dir`` and diff against
    ``baselines_path``. Returns four disjoint lists — see
    :class:`ComparisonResult`. Use :func:`format_comparison` to render
    a human-readable report from the result.
    """
    live = generate_baselines(screenshots_dir)
    stored = load_baselines(baselines_path)

    live_names = set(live.keys())
    stored_names = set(stored.keys())

    match: list[str] = []
    drift: list[str] = []
    for name in sorted(live_names & stored_names):
        if live[name]["sha256"] == stored[name]["sha256"]:
            match.append(name)
        else:
            drift.append(name)

    new = sorted(live_names - stored_names)
    missing = sorted(stored_names - live_names)

    return {
        "match": match,
        "drift": drift,
        "new": new,
        "missing": missing,
    }


def format_comparison(result: ComparisonResult) -> str:
    """Render a short human summary of a comparison for CLI output."""
    lines = [
        f"✓ {len(result['match'])} match",
        f"✗ {len(result['drift'])} drift",
        f"+ {len(result['new'])} new",
        f"- {len(result['missing'])} missing",
    ]
    if result["drift"]:
        lines.append("")
        lines.append("Drifted:")
        lines.extend(f"  • {name}" for name in result["drift"])
    if result["new"]:
        lines.append("")
        lines.append("New (no baseline yet — regenerate after review):")
        lines.extend(f"  • {name}" for name in result["new"])
    if result["missing"]:
        lines.append("")
        lines.append("Missing (baseline for a removed surface — prune or restore):")
        lines.extend(f"  • {name}" for name in result["missing"])
    return "\n".join(lines)


def is_clean(result: ComparisonResult) -> bool:
    """True iff no drift / new / missing entries — everything matched."""
    return not (result["drift"] or result["new"] or result["missing"])
