"""Gemini CLI session adapter.

Source layout (under ~/.gemini/tmp/):
  Legacy single JSON:  ~/.gemini/tmp/session-<id>.json
  Modern JSON:         ~/.gemini/tmp/<project>/chats/<file>.json
  Modern JSONL:        ~/.gemini/tmp/<project>/chats/<file>.jsonl

JSON layout:
  {sessionId, projectHash, startTime, lastUpdated, messages: [...], summary, ...}

JSONL layout:
  line 1: session header (sessionId, projectHash, startTime, lastUpdated, kind)
  N:      either a message ({id, timestamp, type, content, ...})
          or a {"$set": ...} mutation event (skipped — we accept the original
          message as written, which is usually sufficient for transcription).

Message types: "user" or "gemini".
Message content: list[{text}] for user, plain string (or list) for gemini.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from pelib.adapters.base import Adapter, ConvertedSession, Source
from pelib.markdown import slugify


class GeminiCliAdapter(Adapter):
    """Convert Gemini CLI session files (JSON or JSONL) into wiki transcripts."""

    name = "gemini_cli"

    def __init__(self, tmp_dir: Path | None = None) -> None:
        self.tmp_dir = tmp_dir or _default_tmp_dir()

    def discover(self) -> Iterable[Source]:
        if not self.tmp_dir.is_dir():
            return
        seen: set[Path] = set()
        for pattern in ("session-*.json", "session-*.jsonl"):
            for path in sorted(self.tmp_dir.glob(pattern)):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield Source(adapter=self.name, path=path)
        for project_dir in sorted(p for p in self.tmp_dir.iterdir() if p.is_dir()):
            chats = project_dir / "chats"
            if not chats.is_dir():
                continue
            for path in sorted(chats.rglob("*.jsonl")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield Source(adapter=self.name, path=path)
            for path in sorted(chats.rglob("*.json")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield Source(adapter=self.name, path=path)

    def convert(self, source: Source) -> ConvertedSession | None:
        suffix = source.path.suffix.lower()
        if suffix == ".jsonl":
            meta, messages = _parse_jsonl(source.path)
        elif suffix == ".json":
            meta, messages = _parse_json(source.path)
        else:
            return None
        if not messages:
            return None
        if not meta.get("sessionId"):
            return None

        meta["project"] = _project_from_path(source.path, self.tmp_dir)
        body_lines = _render_body(messages, meta)
        if not body_lines:
            return None

        return ConvertedSession(
            source=source,
            output_relative=_output_path(meta),
            frontmatter=_build_frontmatter(meta, source.path),
            body="\n".join(body_lines),
        )


# --- discovery helpers -------------------------------------------------------


def _default_tmp_dir() -> Path:
    env = os.environ.get("GEMINI_HOME")
    if env:
        return (Path(env).expanduser() / "tmp").resolve()
    return (Path.home() / ".gemini" / "tmp").resolve()


def _project_from_path(path: Path, tmp_dir: Path) -> str:
    try:
        rel = path.relative_to(tmp_dir)
    except ValueError:
        return ""
    parts = rel.parts
    if not parts:
        return ""
    # legacy: session-*.json directly under tmp/
    if parts[0].startswith("session-"):
        return ""
    return parts[0]


# --- parsing -----------------------------------------------------------------


def _parse_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if not isinstance(data, dict):
        return {}, []
    meta = _meta_from_header(data)
    msgs = data.get("messages") or []
    if not isinstance(msgs, list):
        msgs = []
    if data.get("summary") and isinstance(data["summary"], str):
        meta["title_hint"] = data["summary"]
    return meta, [m for m in msgs if isinstance(m, dict)]


def _parse_jsonl(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if "$set" in obj:
                    continue  # mutation events; ignored for transcription
                if obj.get("kind") and not meta:
                    meta = _meta_from_header(obj)
                    continue
                if obj.get("type") in ("user", "gemini"):
                    messages.append(obj)
                elif "messages" in obj and isinstance(obj["messages"], list):
                    messages.extend(m for m in obj["messages"] if isinstance(m, dict))
    except OSError:
        return {}, []
    return meta, messages


def _meta_from_header(header: dict[str, Any]) -> dict[str, Any]:
    sid = header.get("sessionId")
    return {
        "sessionId": sid if isinstance(sid, str) else "",
        "started": header.get("startTime") if isinstance(header.get("startTime"), str) else "",
        "ended": header.get("lastUpdated") if isinstance(header.get("lastUpdated"), str) else "",
        "projectHash": header.get("projectHash") if isinstance(header.get("projectHash"), str) else "",
    }


# --- rendering ---------------------------------------------------------------


def _render_body(messages: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:
    project = meta.get("project") or ""
    short = (meta.get("sessionId") or "")[:8]
    started = (meta.get("started") or "")[:10]
    title_hint = meta.get("title_hint", "")

    lines: list[str] = [
        f"# Session: {short} — {started}" if short and started else "# Session",
        "",
    ]
    clean_summary = _clean_title_hint(title_hint)
    bits = [b for b in (
        f"**Project:** `{project}`" if project else None,
        f"**Started:** {started}" if started else None,
        f"**Summary:** {clean_summary}" if clean_summary else None,
    ) if b]
    if bits:
        lines.append(" · ".join(bits))
        lines.append("")
    lines.append("## Conversation")
    lines.append("")

    turn = 0
    model_seen: str | None = None
    for msg in messages:
        role_raw = msg.get("type")
        if role_raw not in ("user", "gemini"):
            continue
        rendered = _render_message(msg)
        if not rendered:
            continue
        turn += 1
        role = "User" if role_raw == "user" else "Assistant"
        lines.append(f"### Turn {turn} — {role}")
        lines.append("")
        lines.append(rendered)
        lines.append("")
        if role_raw == "gemini" and not model_seen:
            model = msg.get("model")
            if isinstance(model, str):
                model_seen = model
    if model_seen:
        meta["model"] = model_seen
    return lines if turn > 0 else []


def _render_message(msg: dict[str, Any]) -> str:
    role = msg.get("type")
    content = msg.get("content")
    parts: list[str] = []

    text = _flatten_content(content)
    if text:
        parts.append(text)

    if role == "gemini":
        thoughts = msg.get("thoughts")
        if isinstance(thoughts, list):
            thought_text = _flatten_thoughts(thoughts)
            if thought_text:
                parts.append(f"<details><summary>thinking</summary>\n\n{thought_text}\n\n</details>")
        tool_calls = msg.get("toolCalls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                rendered = _render_tool_call(tc)
                if rendered:
                    parts.append(rendered)

    return "\n\n".join(p for p in parts if p)


def _flatten_content(content: Any) -> str:
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
        return "\n\n".join(pieces).strip()
    return str(content).strip()


def _flatten_thoughts(thoughts: list[Any]) -> str:
    pieces: list[str] = []
    for t in thoughts:
        if not isinstance(t, dict):
            continue
        subject = t.get("subject") or ""
        description = t.get("description") or ""
        line = f"**{subject}**: {description}" if subject and description else (description or subject)
        if line:
            pieces.append(line.strip())
    return "\n\n".join(pieces)


def _render_tool_call(tc: Any) -> str:
    if not isinstance(tc, dict):
        return ""
    name = tc.get("name") or tc.get("toolName") or "tool"
    args = tc.get("arguments") or tc.get("input") or tc.get("params")
    try:
        rendered_args = json.dumps(args, ensure_ascii=False, indent=2) if args is not None else ""
    except (TypeError, ValueError):
        rendered_args = str(args)
    out = tc.get("output") or tc.get("result")
    out_str = ""
    if out is not None:
        try:
            out_str = json.dumps(out, ensure_ascii=False, indent=2) if not isinstance(out, str) else out
        except (TypeError, ValueError):
            out_str = str(out)
    blocks = [f"🔧 **Tool use: `{name}`**"]
    if rendered_args:
        blocks.append(f"```json\n{rendered_args}\n```")
    if out_str:
        truncated = out_str[:2000]
        suffix = "\n…(truncated)" if len(out_str) > 2000 else ""
        blocks.append(f"📤 **Tool result:**\n\n```\n{truncated}{suffix}\n```")
    return "\n\n".join(blocks)


# --- output ------------------------------------------------------------------


def _output_path(meta: dict[str, Any]) -> str:
    date = (meta.get("started") or meta.get("ended") or "")[:10] or "0000-00-00"
    project_slug = slugify(meta.get("project") or "unknown")[:40] or "unknown"
    session_short = (meta.get("sessionId") or "").replace("-", "")[:12] or "000000000000"
    return f"raw/sessions/gemini_cli/{date}-{project_slug}-{session_short}.md"


def _clean_title_hint(hint: str) -> str:
    """Use the session summary as title only when it looks like prose.
    Discard structured/AI-dumped summaries (start with '{', '[', or contain code blocks)."""
    if not hint:
        return ""
    stripped = hint.strip()
    if not stripped:
        return ""
    if stripped[0] in "{[" or "```" in stripped:
        return ""
    # Collapse whitespace including literal "\n" / "\r" / "\t" escape sequences.
    for esc in ("\\n", "\\r", "\\t"):
        stripped = stripped.replace(esc, " ")
    flattened = " ".join(stripped.split())
    return flattened[:120]


def _build_frontmatter(meta: dict[str, Any], source_path: Path) -> dict[str, Any]:
    started = meta.get("started") or ""
    ended = meta.get("ended") or ""
    short = (meta.get("sessionId") or "")[:8]
    title_hint = meta.get("title_hint") or ""
    cleaned_hint = _clean_title_hint(title_hint)
    if cleaned_hint:
        title = cleaned_hint
    else:
        title = f"Session: {short} — {started[:10]}" if short and started else "Session"
    return {
        "title": title,
        "type": "session",
        "date": (started or ended)[:10],
        "adapter": "gemini_cli",
        "sessionId": meta.get("sessionId", ""),
        "project": meta.get("project", ""),
        "started": started,
        "ended": ended,
        "model": meta.get("model", ""),
        "source_file": str(source_path),
    }
