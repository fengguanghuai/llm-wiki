from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pelib.config import Config
from pelib.markdown import score_match, tokenize_query
from pelib.wiki import queryable_files


@dataclass(frozen=True)
class QueryHit:
    score: int
    path: Path
    snippet: str


def search(cfg: Config, text: str, limit: int = 12) -> list[QueryHit]:
    if limit <= 0:
        raise ValueError("limit must be > 0")
    terms = tokenize_query(text)
    if not terms:
        return []
    hits: list[QueryHit] = []
    for path in queryable_files(cfg.wiki_root):
        body = path.read_text(encoding="utf-8", errors="replace")
        score, snippet = score_match(body, terms)
        if score > 0:
            hits.append(QueryHit(score=score, path=path, snippet=snippet))
    hits.sort(key=lambda h: (-h.score, str(h.path).lower()))
    return hits[:limit]
