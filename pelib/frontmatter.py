from __future__ import annotations

from typing import Any


def parse(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _parse_value(value.strip())
    return meta, body


def render(meta: dict[str, Any]) -> str:
    return "\n".join(f"{key}: {_render_value(value)}" for key, value in meta.items())


def _parse_value(value: str) -> Any:
    if value == "":
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items: list[str] = []
        for part in _split_top_level(inner):
            part = part.strip()
            if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"}:
                part = part[1:-1]
            items.append(part)
        return items
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        rendered = ", ".join(f'"{_escape(str(item))}"' for item in value)
        return f"[{rendered}]"
    text = str(value)
    if _needs_quotes(text):
        return f'"{_escape(text)}"'
    return text


def _needs_quotes(value: str) -> bool:
    if value == "":
        return True
    return any(ch in value for ch in (":", "#", "[", "]", "{", "}", ","))


def _escape(value: str) -> str:
    return value.replace('"', "'")


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts
