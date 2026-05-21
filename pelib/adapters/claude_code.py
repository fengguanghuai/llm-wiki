"""Claude Code session adapter.

Source layout (CLAUDE_CONFIG_DIR can override; otherwise both roots are scanned):
  ~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl
  ~/.config/claude/projects/<encoded-cwd>/<sessionId>.jsonl

Each .jsonl is an event stream. We only render the conversational events
(`user` + `assistant`); the rest (attachment / file-history-snapshot /
permission-mode / ai-title / last-prompt / system) carry runtime metadata
that doesn't belong in the transcript.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from pelib.adapters.base import Adapter, ConvertedSession, Source
from pelib.markdown import slugify


CONVO_TYPES: frozenset[str] = frozenset({"user", "assistant"})
SKIP_USER_META: frozenset[str] = frozenset({"<local-command-caveat>", "<command-name>"})


class ClaudeCodeAdapter(Adapter):
    """Convert Claude Code session JSONL files into wiki transcripts."""

    name = "claude_code"

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.roots = roots if roots is not None else _default_roots()

    def discover(self) -> Iterable[Source]:
        for root in self.roots:
            projects = root / "projects"
            if not projects.is_dir():
                continue
            for jsonl in sorted(projects.glob("*/*.jsonl")):
                yield Source(adapter=self.name, path=jsonl)

    def convert(self, source: Source) -> ConvertedSession | None:
        events = list(_read_events(source.path))
        if not events:
            return None

        meta = _extract_meta(events, source.path)
        if not meta.get("sessionId"):
            return None

        body_lines = _render_body(events, meta)
        if not body_lines:
            return None

        output_relative = _output_path(meta)
        frontmatter = _build_frontmatter(meta, source.path)
        body = "\n".join(body_lines)
        return ConvertedSession(
            source=source,
            output_relative=output_relative,
            frontmatter=frontmatter,
            body=body,
        )


# --- discovery helpers --------------------------------------------------------


def _default_roots() -> list[Path]:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return [Path(p).expanduser().resolve() for p in env.split(os.pathsep) if p.strip()]
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return [
        (Path(config_home) / "claude").resolve(),
        (Path.home() / ".claude").resolve(),
    ]


# --- event parsing ------------------------------------------------------------


def _read_events(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _extract_meta(events: list[dict[str, Any]], source_path: Path) -> dict[str, Any]:
    """Pull sessionId / project / cwd / model / started / ended / title from the stream."""
    meta: dict[str, Any] = {}
    title: str | None = None
    for event in events:
        if not meta.get("sessionId") and isinstance(event.get("sessionId"), str):
            meta["sessionId"] = event["sessionId"]
        cwd = event.get("cwd")
        if isinstance(cwd, str) and not meta.get("cwd"):
            meta["cwd"] = cwd
        ts = event.get("timestamp")
        if isinstance(ts, str):
            if not meta.get("started"):
                meta["started"] = ts
            meta["ended"] = ts
        if event.get("type") == "ai-title":
            candidate = event.get("title") or event.get("aiTitle")
            if isinstance(candidate, str) and candidate.strip():
                title = candidate.strip()
        if event.get("type") == "assistant" and not meta.get("model"):
            msg = event.get("message")
            if isinstance(msg, dict):
                model = msg.get("model")
                if isinstance(model, str):
                    meta["model"] = model
    if title:
        meta["title"] = title
    meta.setdefault("sessionId", source_path.stem)
    if meta.get("cwd"):
        meta["project"] = Path(meta["cwd"]).name or meta["cwd"]
    else:
        meta["project"] = ""
    return meta


# --- markdown rendering -------------------------------------------------------


def _render_body(events: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:
    project = meta.get("project") or ""
    model = meta.get("model") or ""
    short = (meta.get("sessionId") or "")[:8]
    started = (meta.get("started") or "")[:10]

    header_bits = [b for b in (f"**Project:** `{project}`" if project else None,
                               f"**Model:** `{model}`" if model else None,
                               f"**Started:** {started}" if started else None) if b]
    lines: list[str] = [
        f"# Session: {short} — {started}" if short and started else f"# Session: {meta.get('sessionId', '?')}",
        "",
    ]
    if header_bits:
        lines.append(" · ".join(header_bits))
        lines.append("")
    lines.append("## Conversation")
    lines.append("")

    turn = 0
    for event in events:
        kind = event.get("type")
        if kind not in CONVO_TYPES:
            continue
        rendered = _render_message_block(event)
        if rendered is None:
            continue
        turn += 1
        role = "User" if kind == "user" else "Assistant"
        lines.append(f"### Turn {turn} — {role}")
        lines.append("")
        lines.append(rendered)
        lines.append("")
    return lines


def _render_message_block(event: dict[str, Any]) -> str | None:
    msg = event.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if isinstance(content, str):
        text = content.strip()
        if not text or any(tag in text for tag in SKIP_USER_META):
            return None
        return text
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = (block.get("text") or "").strip()
            if text:
                parts.append(text)
        elif btype == "thinking":
            text = (block.get("thinking") or block.get("text") or "").strip()
            if text:
                parts.append(f"<details><summary>thinking</summary>\n\n{text}\n\n</details>")
        elif btype == "tool_use":
            name = block.get("name") or "tool"
            inp = block.get("input")
            try:
                rendered_input = json.dumps(inp, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                rendered_input = str(inp)
            parts.append(f"🔧 **Tool use: `{name}`**\n\n```json\n{rendered_input}\n```")
        elif btype == "tool_result":
            text = _flatten_tool_result(block.get("content"))
            if text:
                truncated = text[:2000]
                suffix = "\n…(truncated)" if len(text) > 2000 else ""
                parts.append(f"📤 **Tool result:**\n\n```\n{truncated}{suffix}\n```")
        elif btype == "image":
            parts.append("🖼️ *(image attachment omitted)*")
    if not parts:
        return None
    return "\n\n".join(parts)


def _flatten_tool_result(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        pieces: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    pieces.append(text)
            elif isinstance(block, str):
                pieces.append(block)
        return "\n".join(pieces).strip()
    return str(content)


# --- output path / frontmatter -----------------------------------------------


def _output_path(meta: dict[str, Any]) -> str:
    date = (meta.get("started") or "")[:10] or "0000-00-00"
    project_slug = slugify(meta.get("project") or "unknown")[:40] or "unknown"
    session_short = (meta.get("sessionId") or "").replace("-", "")[:12] or "000000000000"
    filename = f"{date}-{project_slug}-{session_short}.md"
    return f"raw/sessions/claude_code/{filename}"


_ISO_NORMALIZE = re.compile(r"\.\d+(?=[+\-Z])")


def _build_frontmatter(meta: dict[str, Any], source_path: Path) -> dict[str, Any]:
    started = meta.get("started") or ""
    ended = meta.get("ended") or ""
    short = (meta.get("sessionId") or "")[:8]
    title = meta.get("title") or (
        f"Session: {short} — {started[:10]}" if short and started else "Session"
    )
    return {
        "title": title,
        "type": "session",
        "date": (started or ended)[:10],
        "adapter": "claude_code",
        "sessionId": meta.get("sessionId", ""),
        "project": meta.get("project", ""),
        "started": _normalize_iso(started),
        "ended": _normalize_iso(ended),
        "model": meta.get("model", ""),
        "source_file": str(source_path),
    }


def _normalize_iso(value: str) -> str:
    if not value:
        return ""
    return _ISO_NORMALIZE.sub("", value)
