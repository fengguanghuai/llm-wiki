# AI Agent Bootstrap Guide

This repository is meant to be initialized by an AI agent, not by a human
following a long checklist. If a user gives you the GitHub URL for this project,
use this file as the setup contract.

## Goal

Set up one local Personal Execution Library: a small Python CLI plus a local
LLM Wiki root used as durable memory by multiple agents.

## Required Human Inputs

Ask for these only if they are not already provided:

1. The local wiki root path.
   - Recommended default: `~/Documents/LLM-WIKI Vault`
2. A short title for a new wiki.
   - Recommended default: `Personal Execution Library`
3. Whether to link the shared skill into local agent skill directories.
   - Recommended default: yes for Codex and Claude Code.

Do not ask the human to run setup commands. After you have these answers, run
the commands yourself.

## Initialization Command

From the repository root, run:

```bash
python3 -m pelib.cli init --wiki-root "<wiki-root>" --title "<wiki-title>" --link-agents
```

If `pelib.toml` already exists and the user explicitly wants to replace it, add:

```bash
--overwrite-config
```

The command is idempotent. It creates missing config, wiki folders, schema files,
and the generated shared agent skill under `.pelib/agent-skill`, while
preserving existing wiki content.

## Validation

After initialization, run:

```bash
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m unittest discover -s tests -v
```

If optional Node tools are requested, verify Node.js/npm first, then run:

```bash
python3 -m pelib.cli skill-web-build --install
python3 -m pelib.cli skill-web-serve --port 4175
```

For the Obsidian plugin, ask for the Obsidian vault path and run:

```bash
python3 -m pelib.cli skill-obsidian-link "<obsidian-vault>" --install
```

## Safety Rules

- Never bulk-import a personal Obsidian vault, browser export, or agent session
  archive without explicit user approval.
- Prefer `sync --dry-run` before any sync that writes files.
- Keep `raw/` immutable after conversion.
- Write durable conclusions through `capture`, `promote`, or curated pages under
  `wiki/`.
- Preserve existing `pelib.toml`, `CLAUDE.md`, `AGENTS.md`, and wiki pages unless
  the user explicitly asks to replace them.

## Main Commands

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli capture "A durable conclusion"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli query "search terms"
python3 -m pelib.cli obsidian-import "<explicit-path>" --dry-run
```
