from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pelib import frontmatter, log, memory
from pelib.config import Config
from pelib.markdown import slugify, title_slug
from pelib.wiki import TYPE_DIRS


@dataclass(frozen=True)
class InboxNote:
    path: Path
    meta: dict[str, Any]
    body: str


def capture(
    cfg: Config,
    text: str,
    *,
    title: str | None,
    tags: list[str],
    confidence: float | None,
) -> Path:
    inbox_dir = cfg.wiki_root / "wiki" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    safe_title = (title or text[:80]).replace("\n", " ").strip() or "note"
    slug = slugify(title or text)[:60] or "note"
    path = inbox_dir / f"{now.strftime('%Y%m%d-%H%M%S')}-{slug}.md"

    meta: dict[str, Any] = {
        "title": safe_title,
        "type": "inbox-note",
        "created": now.isoformat(timespec="seconds"),
        "tags": ["inbox", "agent-capture", *tags],
        "status": "open",
    }
    if confidence is not None:
        meta["confidence"] = f"{confidence:.2f}"

    body = (
        f"# {safe_title}\n\n"
        f"## Captured Conclusion\n\n{text}\n\n"
        f"## Next Action\n\n"
        f"- [ ] Review and promote into `wiki/concepts/`, `wiki/entities/`, "
        f"`wiki/projects/`, or `wiki/MEMORY.md`.\n"
    )
    path.write_text(f"---\n{frontmatter.render(meta)}\n---\n\n{body}", encoding="utf-8")
    log.append(cfg.wiki_root, now, f"capture | {path.relative_to(cfg.wiki_root)}")
    return path


def list_notes(cfg: Config) -> list[InboxNote]:
    folder = cfg.wiki_root / "wiki" / "inbox"
    if not folder.exists():
        return []
    notes: list[InboxNote] = []
    for path in sorted(folder.glob("*.md")):
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        notes.append(InboxNote(path=path, meta=meta, body=body))
    return notes


def find_matches(cfg: Config, selector: str) -> list[InboxNote]:
    candidate = Path(selector).expanduser()
    if not candidate.is_absolute():
        candidate = cfg.wiki_root / "wiki" / "inbox" / selector
    if candidate.exists() and candidate.is_file():
        meta, body = frontmatter.parse(candidate.read_text(encoding="utf-8"))
        return [InboxNote(path=candidate, meta=meta, body=body)]

    matches: list[InboxNote] = []
    for note in list_notes(cfg):
        rel = str(note.path.relative_to(cfg.wiki_root))
        title = str(note.meta.get("title", ""))
        if selector in note.path.name or selector in rel or selector in title:
            matches.append(note)
    return matches


def promote(
    cfg: Config,
    note: InboxNote,
    *,
    target_type: str,
    title: str | None,
    append: bool,
    confidence: float | None,
) -> tuple[Path, str]:
    now = datetime.now()
    note_title = title or note.meta.get("title") or note.path.stem
    conclusion = _extract_section(note.body, "Captured Conclusion").strip() or note.body.strip()
    if not conclusion:
        raise ValueError(f"note has no content: {note.path}")
    final_conf = confidence if confidence is not None else _meta_confidence(note.meta)

    if target_type == "memory":
        target = cfg.wiki_root / "wiki" / "MEMORY.md"
        memory.append_section(target, note_title, conclusion, note.path, now, final_conf)
        label = "wiki/MEMORY.md"
    else:
        target = _target_page(cfg, target_type, note_title)
        if target.exists() and not append:
            raise FileExistsError(f"target exists, use --append: {target}")
        _write_page(target, target_type, note_title, conclusion, note.path, now, append, final_conf)
        label = str(target.relative_to(cfg.wiki_root))

    _mark_promoted(note.path, label, now, final_conf)
    log.append(cfg.wiki_root, now, f"promote | {note.path.relative_to(cfg.wiki_root)} -> {label}")
    return target, label


def promote_batch(
    cfg: Config,
    *,
    target_type: str,
    append: bool,
    limit: int,
    dry_run: bool,
    confidence: float | None,
) -> tuple[int, int, list[str]]:
    notes = [n for n in list_notes(cfg) if n.meta.get("status", "open") == "open"]
    if limit > 0:
        notes = notes[:limit]
    if not notes:
        return 0, 0, ["No open inbox notes."]

    promoted = 0
    errors = 0
    lines: list[str] = []
    now = datetime.now()
    for note in notes:
        rel = note.path.relative_to(cfg.wiki_root)
        note_title = note.meta.get("title") or note.path.stem
        conclusion = _extract_section(note.body, "Captured Conclusion").strip() or note.body.strip()
        if not conclusion:
            lines.append(f"skip {rel}: empty note body")
            errors += 1
            continue
        final_conf = confidence if confidence is not None else _meta_confidence(note.meta)

        if target_type == "memory":
            target = cfg.wiki_root / "wiki" / "MEMORY.md"
            label = "wiki/MEMORY.md"
            if not dry_run:
                memory.append_section(target, note_title, conclusion, note.path, now, final_conf)
        else:
            target = _target_page(cfg, target_type, note_title)
            label = str(target.relative_to(cfg.wiki_root))
            if target.exists() and not append:
                lines.append(f"skip {rel}: target exists ({label}), rerun with --append")
                errors += 1
                continue
            if not dry_run:
                _write_page(target, target_type, note_title, conclusion, note.path, now, append, final_conf)

        if dry_run:
            lines.append(f"[dry-run] {rel} -> {label}")
        else:
            _mark_promoted(note.path, label, now, final_conf)
            log.append(cfg.wiki_root, now, f"promote | {rel} -> {label}")
            lines.append(f"promoted {rel} -> {label}")
        promoted += 1
    return promoted, errors, lines


# Internal --------------------------------------------------------------------

_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)


def _meta_confidence(meta: dict[str, Any]) -> float | None:
    raw = meta.get("confidence")
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if 0.0 <= v <= 1.0 else None


def _extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    m = pattern.search(body)
    if not m:
        return ""
    rest = body[m.end() :]
    nxt = _SECTION_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _target_page(cfg: Config, target_type: str, title: str) -> Path:
    folder = TYPE_DIRS[target_type]
    slug = title_slug(title) if target_type in {"concept", "entity"} else slugify(title)
    return cfg.wiki_root / "wiki" / folder / f"{slug}.md"


def _write_page(
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
        conf_line = f"Confidence: {confidence:.2f}\n\n" if confidence is not None else ""
        with target.open("a", encoding="utf-8") as f:
            f.write(
                f"\n## Update - {now.date().isoformat()}\n\n"
                f"Source: [[{source.stem}]]\n\n"
                f"{conf_line}"
                f"{conclusion.strip()}\n"
            )
        return

    meta: dict[str, Any] = {
        "title": title,
        "type": target_type,
        "created": now.date().isoformat(),
        "updated": now.date().isoformat(),
        "sources": [source.stem],
        "tags": ["promoted", "agent-capture"],
    }
    if confidence is not None:
        meta["confidence"] = f"{confidence:.2f}"

    body = (
        f"# {title}\n\n"
        f"## Summary\n\n{conclusion.strip()}\n\n"
        f"## Connections\n\n- [[{source.stem}]] - captured inbox source.\n"
    )
    target.write_text(f"---\n{frontmatter.render(meta)}\n---\n\n{body}", encoding="utf-8")


def _mark_promoted(path: Path, label: str, now: datetime, confidence: float | None) -> None:
    meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
    meta["status"] = "promoted"
    meta["promoted_at"] = now.isoformat(timespec="seconds")
    meta["promoted_to"] = label
    if confidence is not None:
        meta["promoted_confidence"] = f"{confidence:.2f}"
    path.write_text(
        f"---\n{frontmatter.render(meta)}\n---\n{body.rstrip()}\n\n"
        f"## Promotion\n\n"
        f"- Promoted at: {now.isoformat(timespec='seconds')}\n"
        f"- Promoted to: `{label}`\n",
        encoding="utf-8",
    )
