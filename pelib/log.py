from __future__ import annotations

from datetime import datetime
from pathlib import Path


def append(wiki_root: Path, now: datetime, message: str) -> None:
    log_path = wiki_root / "wiki" / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# Log\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## [{now.strftime('%Y-%m-%d')}] {message}\n")
