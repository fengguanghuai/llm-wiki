# Personal Execution Library

This project is a thin integration layer over two upstream ideas:

- `Pratiyush/llm-wiki`: session sync, static-site generation, adapters, and wiki outputs.
- `lewislulu/llm-wiki-skill`: agent workflow rules for ingest, query, lint, audit, and feedback.

The goal is one central local wiki shared by every agent, not one duplicated wiki per agent.

## Current Center

The central wiki is:

```text
/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki
```

This integration project does not move or copy that wiki. It only wraps it and installs a shared thin skill that points agents back to it.

## Commands

Run from this directory:

```bash
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "A durable conclusion or decision"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli build
python3 -m pelib.cli serve --port 8765
python3 -m pelib.cli link-agents
```

If installed editable:

```bash
pip install -e .
pel status
pel sync --dry-run
pel sync
pel capture "A durable conclusion or decision"
pel inbox
pel promote <inbox-note> --to memory
pel build
pel serve
pel link-agents
```

`pel sync` intentionally runs only `claude_code`, `codex_cli`, and `copilot-chat`
by default. The upstream `obsidian` adapter can ingest the entire vault,
including the wiki itself, so it is opt-in:

```bash
python3 -m pelib.cli sync --all --dry-run
python3 -m pelib.cli sync --adapter obsidian --dry-run
```

## Agent Sharing Model

`pel link-agents` creates symlinks:

```text
~/.codex/skills/personal-execution-library -> ./agent-skill
~/.claude/skills/personal-execution-library -> ./agent-skill
```

That skill contains only instructions and absolute paths. The durable knowledge stays in the central wiki.

## What This Solves

- AI conversations and conclusions can be synced into one LLM Wiki.
- Codex, Claude Code, and other agents can read the same wiki.
- The wiki can still be opened in Obsidian.
- The static site from `llmwiki build` remains available.
- No duplicate per-agent knowledge bases.

## Capturing Conclusions

Use `capture` for durable conclusions that should not be lost in chat history:

```bash
python3 -m pelib.cli capture "Starship should be managed by chezmoi and restored through Brewfile." --tag dotfiles
```

This writes a note under:

```text
<wiki-root>/wiki/inbox/
```

The inbox is intentionally separate from polished pages. An agent can later
review inbox notes and promote them into `wiki/MEMORY.md`, `wiki/concepts/`,
`wiki/entities/`, or `wiki/projects/`.

Review open notes:

```bash
python3 -m pelib.cli inbox
```

Promote one note:

```bash
python3 -m pelib.cli promote 20260420-120000-example.md --to memory
python3 -m pelib.cli promote "starship" --to concept --title "Starship Prompt"
python3 -m pelib.cli promote "dotfiles" --to project --title "Dotfiles"
```

Promotion keeps the original inbox note and marks it as `status: promoted`
with a `promoted_to` field, so the knowledge remains traceable.

## What This Does Not Do Yet

- It does not rewrite the upstream `llmwiki` engine.
- It does not store secrets or agent tokens.
- It does not merge multiple Obsidian vaults.
- It runs the upstream `Pratiyush/llm-wiki` code while overriding `REPO_ROOT`
  to point at your central Obsidian wiki. This avoids modifying the existing
  wiki checkout even if its bundled Python package is incomplete or stale.

## Suggested Next Milestones

1. Add an Obsidian whitelist import command that avoids recursively ingesting the whole vault.
2. Add a richer query helper that reads index/overview/hot/MEMORY and prints candidate pages.
3. Add a batch promote workflow for reviewing all open inbox notes.
4. Add a web/Obsidian feedback path using the audit format from `llm-wiki-skill`.
