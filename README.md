# Personal Execution Library

One local command-line wrapper for turning AI-agent conversations and selected notes into a shared LLM Wiki.

This repository contains:

- `pelib/` — the `pel` CLI and local workflow commands.
- `llmwiki/` — a bundled, conversion-focused subset of upstream `llm-wiki`.
- `llm-wiki-skill/` — optional web viewer and Obsidian audit tooling.

Upstream attribution and boundaries are documented in [docs/VENDORED_PROJECTS.md](docs/VENDORED_PROJECTS.md).

## What It Does

- Converts local agent sessions into Markdown under a configured wiki root.
- Provides inbox-style capture and promotion workflows for durable notes.
- Searches curated wiki pages for quick recall.
- Imports explicit Obsidian files or folders by whitelist.
- Optionally serves the bundled `llm-wiki-skill` web viewer.

## Requirements

- Python 3.9+
- Git
- Node.js/npm only for optional `llm-wiki-skill` web or Obsidian plugin commands

## Setup

Create a local config from the example:

```bash
cp pelib.example.toml pelib.toml
```

Edit `pelib.toml` and set your local wiki path:

```toml
[paths]
wiki_root = "~/Documents/LLM-WIKI Vault"
llm_wiki_skill_repo = "./llm-wiki-skill"
```

The wiki root should contain the normal LLM Wiki folders/files:

```text
raw/
wiki/
site/
CLAUDE.md
AGENTS.md
```

## Run

Without installing:

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
```

Or install as an editable local CLI:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pel status
pel sync --dry-run
```

## Core Workflows

### Sync Agent Sessions

Default sync adapters are intentionally limited:

- `claude_code`
- `codex_cli`
- `copilot-chat`

```bash
pel sync --dry-run
pel sync
```

Run a specific adapter:

```bash
pel sync --adapter codex_cli --dry-run
```

Obsidian is opt-in:

```bash
pel obsidian-import "daily-logs/2026-03-25" --dry-run
```

### Capture And Promote Knowledge

```bash
pel capture "A durable conclusion"
pel inbox
pel promote <inbox-note> --to memory
pel promote-batch --to memory --dry-run
pel query "starship dotfiles"
```

### Feedback Loop

```bash
pel feedback "Needs clearer source links" --from web --target "wiki/MEMORY.md" --verdict needs-work
pel feedback-inbox
```

### Optional Web / Obsidian Tooling

```bash
pel skill-web-build --install
pel skill-web-serve --port 4175
pel skill-obsidian-build --install
pel skill-obsidian-link "/path/to/your/Obsidian vault"
```

## Agent Skill Sharing

Link the shared skill into local agent skill directories:

```bash
pel link-agents
```

This creates symlinks such as:

- `~/.codex/skills/personal-execution-library -> ./agent-skill`
- `~/.claude/skills/personal-execution-library -> ./agent-skill`

Durable knowledge stays in the configured wiki root, not inside agent-local skill folders.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Repository Hygiene

Do not commit local wiki contents, virtual environments, generated package metadata, `node_modules`, or build outputs. Keep personal paths in `pelib.toml`, which is intentionally ignored.
