from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


STATE_VERSION = 1
STATE_FILENAME = ".pel-state.json"


@dataclass(frozen=True)
class SourceState:
    sha1: str
    mtime: float
    output: str  # relative to wiki_root


class State:
    """Per-source incremental-sync state, persisted as .pel-state.json under wiki_root."""

    def __init__(self, path: Path, sources: dict[str, SourceState] | None = None) -> None:
        self.path = path
        self._sources: dict[str, SourceState] = dict(sources or {})

    @classmethod
    def load(cls, wiki_root: Path) -> "State":
        path = wiki_root / STATE_FILENAME
        if not path.exists():
            return cls(path)
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(path)
        raw_sources = data.get("sources", {})
        sources: dict[str, SourceState] = {}
        for key, value in raw_sources.items():
            if not isinstance(value, dict):
                continue
            try:
                sources[key] = SourceState(
                    sha1=str(value.get("sha1", "")),
                    mtime=float(value.get("mtime", 0.0)),
                    output=str(value.get("output", "")),
                )
            except (TypeError, ValueError):
                continue
        return cls(path, sources)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "sources": {key: asdict(state) for key, state in self._sources.items()},
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def get(self, key: str) -> SourceState | None:
        return self._sources.get(key)

    def set(self, key: str, source_state: SourceState) -> None:
        self._sources[key] = source_state

    def remove(self, key: str) -> None:
        self._sources.pop(key, None)

    def keys(self) -> list[str]:
        return list(self._sources.keys())

    def __len__(self) -> int:
        return len(self._sources)
