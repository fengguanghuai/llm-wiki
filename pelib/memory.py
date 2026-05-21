from __future__ import annotations

from datetime import datetime
from pathlib import Path


def append_section(
    memory_path: Path,
    title: str,
    body: str,
    source: Path,
    now: datetime,
    confidence: float | None,
) -> None:
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if not memory_path.exists():
        memory_path.write_text("# MEMORY\n", encoding="utf-8")
    conf_line = f"- Confidence: {confidence:.2f}\n" if confidence is not None else ""
    with memory_path.open("a", encoding="utf-8") as f:
        f.write(
            f"\n## {title}\n\n"
            f"- Date: {now.date().isoformat()}\n"
            f"- Source: [[{source.stem}]]\n\n"
            f"{conf_line}"
            f"{body.strip()}\n"
        )
