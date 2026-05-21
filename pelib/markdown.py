from __future__ import annotations

import re
from collections import Counter


_CJK = re.compile(r"[一-鿿]")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9一-鿿]+", "-", text)
    return text.strip("-") or "note"


def title_slug(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9一-鿿]+", text)
    if not parts:
        return "Untitled"
    if any(_CJK.search(part) for part in parts):
        return "".join(parts)
    return "".join(part[:1].upper() + part[1:] for part in parts)


def tokenize_query(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+|[一-鿿]+", text.lower())
    return [term for term in raw if len(term) > 1 or _CJK.search(term)]


def score_match(body: str, terms: list[str]) -> tuple[int, str]:
    lowered = body.lower()
    counts: Counter[str] = Counter()
    for term in terms:
        n = lowered.count(term)
        if n:
            counts[term] = n
    if not counts:
        return 0, ""
    score = len(counts) * 10 + sum(min(c, 5) for c in counts.values())
    return score, best_snippet(body, list(counts.keys()))


def best_snippet(body: str, terms: list[str]) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return "(empty file)"
    lowered = [t.lower() for t in terms]
    for line in lines:
        low = line.lower()
        if any(t in low for t in lowered):
            return re.sub(r"\s+", " ", line)[:180]
    return re.sub(r"\s+", " ", lines[0])[:180]
