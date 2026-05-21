"""Sync orchestrator: discover sources, decide what's new, convert, persist state."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pelib import adapters, log
from pelib.adapters.base import Adapter, AdapterStats, Source
from pelib.config import Config
from pelib.state import SourceState, State


@dataclass
class SyncResult:
    per_adapter: dict[str, AdapterStats]

    @property
    def total_converted(self) -> int:
        return sum(s.converted for s in self.per_adapter.values())

    @property
    def total_errored(self) -> int:
        return sum(s.errored for s in self.per_adapter.values())


def sync(
    cfg: Config,
    *,
    adapter_names: list[str] | None = None,
    dry_run: bool = False,
) -> SyncResult:
    if not cfg.wiki_root.exists():
        raise FileNotFoundError(f"wiki root does not exist: {cfg.wiki_root}")

    if adapter_names:
        names = list(adapter_names)
        unknown = [n for n in names if n not in adapters.REGISTRY]
        if unknown:
            raise KeyError(f"unknown adapter(s): {', '.join(unknown)}")
    else:
        names = [n for n in cfg.default_sync_adapters if n in adapters.REGISTRY]
        if not names:
            raise KeyError(
                "no registered adapters in default_sync_adapters="
                f"{list(cfg.default_sync_adapters)}; "
                f"known adapters: {adapters.names()}"
            )

    state = State.load(cfg.wiki_root)
    per_adapter: dict[str, AdapterStats] = {}
    now = datetime.now()

    for name in names:
        adapter = adapters.get(name)()
        per_adapter[name] = _run_adapter(adapter, cfg, state, dry_run)

    if not dry_run:
        state.save()

    total = sum(s.converted for s in per_adapter.values())
    if not dry_run and total > 0:
        log.append(cfg.wiki_root, now, f"sync | {total} session(s) converted")

    return SyncResult(per_adapter=per_adapter)


def _run_adapter(adapter: Adapter, cfg: Config, state: State, dry_run: bool) -> AdapterStats:
    discovered = 0
    converted = 0
    unchanged = 0
    skipped = 0
    errored = 0
    errors: list[str] = []

    for source in adapter.discover():
        discovered += 1
        try:
            current = _fingerprint(source.path)
        except OSError as exc:
            errored += 1
            errors.append(f"{source.path}: {exc}")
            continue

        prior = state.get(source.state_key)
        if prior and prior.sha1 == current.sha1 and _output_exists(cfg, prior.output):
            unchanged += 1
            continue

        try:
            result = adapter.convert(source)
        except Exception as exc:  # noqa: BLE001 — adapters may raise anything
            errored += 1
            errors.append(f"{source.path}: {exc}")
            continue

        if result is None:
            skipped += 1
            continue

        if not dry_run:
            output_path = cfg.wiki_root / result.output_relative
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.render(), encoding="utf-8")
            state.set(
                source.state_key,
                SourceState(
                    sha1=current.sha1,
                    mtime=current.mtime,
                    output=result.output_relative,
                ),
            )
        converted += 1

    return AdapterStats(
        discovered=discovered,
        converted=converted,
        unchanged=unchanged,
        skipped=skipped,
        errored=errored,
        errors=errors,
    )


@dataclass(frozen=True)
class _Fingerprint:
    sha1: str
    mtime: float


def _fingerprint(path: Path) -> _Fingerprint:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return _Fingerprint(sha1=h.hexdigest(), mtime=path.stat().st_mtime)


def _output_exists(cfg: Config, relative: str) -> bool:
    if not relative:
        return False
    return (cfg.wiki_root / relative).exists()
