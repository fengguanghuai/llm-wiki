"""Codex CLI session adapter.

Source layout (CODEX_HOME can override; otherwise ~/.codex):
  ~/.codex/sessions/<Y>/<M>/<D>/rollout-*.jsonl
  ~/.codex/archived_sessions/*.jsonl

Each .jsonl is an event stream where every line is
  {"timestamp": ..., "type": ..., "payload": {...}}

Relevant types for transcription:
  session_meta   — once at the head; carries id, cwd, model_provider, git
  turn_context   — carries model for the upcoming turn
  response_item  — the actual conversation content
                   payload.role in {user, assistant, developer}
                   payload.type in {message, function_call, function_call_output,
                                    reasoning, custom_tool_call,
                                    custom_tool_call_output, web_search_call}
  event_msg      — runtime events (token_count etc.); skipped
  compacted      — context-compaction marker; skipped
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from pelib.adapters.base import Adapter, ConvertedSession, Source
from pelib.markdown import slugify


# Suppressed because they're not user content:
_ENV_CONTEXT_RE = re.compile(r"<environment_context>.*?</environment_context>", re.DOTALL)


class CodexCliAdapter(Adapter):
    """Convert Codex CLI session JSONL files into wiki transcripts."""

    name = "codex_cli"

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or _default_home()

    def discover(self) -> Iterable[Source]:
        seen: set[Path] = set()
        for root in (self.home / "sessions", self.home / "archived_sessions"):
            if not root.is_dir():
                continue
            for jsonl in sorted(root.rglob("*.jsonl")):
                resolved = jsonl.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
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

        return ConvertedSession(
            source=source,
            output_relative=_output_path(meta),
            frontmatter=_build_frontmatter(meta, source.path),
            body="\n".join(body_lines),
        )


# --- discovery ---------------------------------------------------------------


def _default_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


# --- parsing -----------------------------------------------------------------


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
    meta: dict[str, Any] = {}
    for event in events:
        kind = event.get("type")
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if kind == "session_meta":
            sid = payload.get("id")
            if isinstance(sid, str):
                meta.setdefault("sessionId", sid)
            ts = payload.get("timestamp") or event.get("timestamp")
            if isinstance(ts, str):
                meta.setdefault("started", ts)
            cwd = payload.get("cwd")
            if isinstance(cwd, str):
                meta.setdefault("cwd", cwd)
        elif kind == "turn_context" and not meta.get("model"):
            model = payload.get("model")
            if isinstance(model, str):
                meta["model"] = model
            # turn_context's cwd is per-turn but is a reasonable fallback
            cwd = payload.get("cwd")
            if isinstance(cwd, str):
                meta.setdefault("cwd", cwd)

        ts = event.get("timestamp")
        if isinstance(ts, str):
            meta.setdefault("started", ts)
            meta["ended"] = ts

    if meta.get("cwd"):
        meta["project"] = Path(meta["cwd"]).name or meta["cwd"]
    else:
        meta["project"] = ""
    meta.setdefault("sessionId", source_path.stem)
    return meta


# --- rendering ---------------------------------------------------------------


def _render_body(events: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:
    project = meta.get("project") or ""
    model = meta.get("model") or ""
    short = (meta.get("sessionId") or "")[:8]
    started = (meta.get("started") or "")[:10]

    header_bits = [b for b in (
        f"**Project:** `{project}`" if project else None,
        f"**Model:** `{model}`" if model else None,
        f"**Started:** {started}" if started else None,
    ) if b]
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
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        rendered, role = _render_item(payload)
        if rendered is None:
            continue
        turn += 1
        lines.append(f"### Turn {turn} — {role}")
        lines.append("")
        lines.append(rendered)
        lines.append("")
    return lines if turn > 0 else []


def _render_item(payload: dict[str, Any]) -> tuple[str | None, str]:
    item_type = payload.get("type")
    role = (payload.get("role") or "").lower()

    if item_type == "message":
        if role == "developer":
            return None, ""  # system/developer noise, skip
        text = _flatten_message_content(payload.get("content"))
        if not text:
            return None, ""
        # Filter user-side env context wrapper
        stripped = _ENV_CONTEXT_RE.sub("", text).strip()
        if not stripped:
            return None, ""
        return stripped, "Assistant" if role == "assistant" else "User"

    if item_type in ("function_call", "custom_tool_call"):
        name = payload.get("name") or "tool"
        try:
            args = json.loads(payload.get("arguments") or "null")
            rendered = json.dumps(args, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            rendered = str(payload.get("arguments", ""))
        text = f"🔧 **Tool use: `{name}`**\n\n```json\n{rendered}\n```"
        return text, "Assistant"

    if item_type in ("function_call_output", "custom_tool_call_output"):
        out = payload.get("output")
        text = _stringify_tool_output(out)
        if not text.strip():
            return None, ""
        truncated = text[:2000]
        suffix = "\n…(truncated)" if len(text) > 2000 else ""
        return f"📤 **Tool result:**\n\n```\n{truncated}{suffix}\n```", "User"

    if item_type == "reasoning":
        # Codex usually stores reasoning as encrypted_content; skip unless plaintext.
        content = payload.get("content")
        summary = payload.get("summary")
        if isinstance(summary, list) and summary:
            text = "\n".join(str(s) for s in summary if s).strip()
            if text:
                return f"<details><summary>reasoning</summary>\n\n{text}\n\n</details>", "Assistant"
        if isinstance(content, str) and content.strip():
            return f"<details><summary>reasoning</summary>\n\n{content.strip()}\n\n</details>", "Assistant"
        return None, ""

    if item_type == "web_search_call":
        query = payload.get("action", {}).get("query") if isinstance(payload.get("action"), dict) else None
        return f"🔍 **Web search**: `{query}`" if query else None, "Assistant"

    return None, ""


def _flatten_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n\n".join(parts)
    return str(content)


def _stringify_tool_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(value)


# --- output ------------------------------------------------------------------


def _output_path(meta: dict[str, Any]) -> str:
    date = (meta.get("started") or "")[:10] or "0000-00-00"
    project_slug = slugify(meta.get("project") or "unknown")[:40] or "unknown"
    session_short = (meta.get("sessionId") or "").replace("-", "")[:12] or "000000000000"
    return f"raw/sessions/codex_cli/{date}-{project_slug}-{session_short}.md"


_ISO_NORMALIZE = re.compile(r"\.\d+(?=[+\-Z])")


def _build_frontmatter(meta: dict[str, Any], source_path: Path) -> dict[str, Any]:
    started = meta.get("started") or ""
    ended = meta.get("ended") or ""
    short = (meta.get("sessionId") or "")[:8]
    title = f"Session: {short} — {started[:10]}" if short and started else "Session"
    return {
        "title": title,
        "type": "session",
        "date": (started or ended)[:10],
        "adapter": "codex_cli",
        "sessionId": meta.get("sessionId", ""),
        "project": meta.get("project", ""),
        "started": _ISO_NORMALIZE.sub("", started),
        "ended": _ISO_NORMALIZE.sub("", ended),
        "model": meta.get("model", ""),
        "source_file": str(source_path),
    }
