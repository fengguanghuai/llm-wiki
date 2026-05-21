from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pelib import log
from pelib.config import Config


def record(cfg: Config, page: str, message: str) -> Path:
    page = page.strip()
    if not page:
        raise ValueError("page must be non-empty")
    message = message.strip()
    if not message:
        raise ValueError("correction message must be non-empty")

    page_path = Path(page).expanduser()
    if not page_path.is_absolute():
        page_path = cfg.wiki_root / page
    if not page_path.exists():
        raise FileNotFoundError(f"page does not exist: {page_path}")

    rel = page_path.relative_to(cfg.wiki_root)
    now = datetime.now()
    log.append(cfg.wiki_root, now, f"correct | {rel} | {message}")
    return page_path
