from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Source:
    """A single source file an adapter can convert into a wiki session note."""

    adapter: str
    path: Path

    @property
    def state_key(self) -> str:
        return f"{self.adapter}:{self.path}"


@dataclass(frozen=True)
class ConvertedSession:
    """The output of an adapter for one source."""

    source: Source
    output_relative: str   # path relative to wiki_root, e.g. "raw/sessions/claude_code/<file>.md"
    frontmatter: dict[str, Any]
    body: str

    def render(self) -> str:
        from pelib import frontmatter as fm
        return f"---\n{fm.render(self.frontmatter)}\n---\n\n{self.body.rstrip()}\n"


@dataclass(frozen=True)
class AdapterStats:
    discovered: int = 0
    converted: int = 0
    unchanged: int = 0
    skipped: int = 0
    errored: int = 0
    errors: list[str] = field(default_factory=list)


class Adapter(ABC):
    """Protocol every session adapter must implement."""

    name: str = ""

    @abstractmethod
    def discover(self) -> Iterable[Source]:
        """Yield every source file currently reachable."""

    @abstractmethod
    def convert(self, source: Source) -> ConvertedSession | None:
        """Parse one source file. Return None if the file should be silently skipped
        (e.g. empty, malformed in a known harmless way)."""
