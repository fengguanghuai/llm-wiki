"""llmwiki — LLM-powered knowledge base from Claude Code, Codex CLI, Cursor,
Gemini CLI, and Obsidian sessions.

Follows Andrej Karpathy's LLM Wiki pattern:
    https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Public API:
    - llmwiki.cli.main()              — the command-line entry point
    - llmwiki.convert.convert_all()   — .jsonl → markdown
    - llmwiki.adapters.REGISTRY       — adapter registry
"""

__version__ = "1.1.0rc2"
__author__ = "Pratiyush"
__license__ = "MIT"

from pathlib import Path

# Repo root (llmwiki/ clone), resolved from this file's location.
REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent
