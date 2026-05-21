from __future__ import annotations

from pelib.adapters.base import Adapter, AdapterStats, ConvertedSession, Source
from pelib.adapters.claude_code import ClaudeCodeAdapter
from pelib.adapters.codex_cli import CodexCliAdapter
from pelib.adapters.gemini_cli import GeminiCliAdapter


REGISTRY: dict[str, type[Adapter]] = {
    "claude_code": ClaudeCodeAdapter,
    "codex_cli": CodexCliAdapter,
    "gemini_cli": GeminiCliAdapter,
}


def get(name: str) -> type[Adapter]:
    if name not in REGISTRY:
        raise KeyError(f"unknown adapter: {name}")
    return REGISTRY[name]


def names() -> list[str]:
    return sorted(REGISTRY.keys())


__all__ = [
    "Adapter",
    "AdapterStats",
    "ConvertedSession",
    "Source",
    "ClaudeCodeAdapter",
    "CodexCliAdapter",
    "GeminiCliAdapter",
    "REGISTRY",
    "get",
    "names",
]
