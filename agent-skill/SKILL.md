---
name: personal-execution-library
description: >-
  Use this skill when the user asks to remember, ingest, query, update, audit,
  or reuse knowledge from a shared local LLM Wiki / execution library.
---

# Personal Execution Library

This is a thin shared skill template. Do not create an agent-specific knowledge
base. Use the configured central wiki for durable memory.

## Setup

For a local installation, initialize the repository with:

```bash
python3 -m pelib.cli init --wiki-root "~/Documents/LLM-WIKI Vault" --title "Personal Execution Library" --link-agents
```

This writes the generated local skill to `.pelib/agent-skill/` and links agents
to that generated copy. The tracked `agent-skill/SKILL.md` file is only a
source template.

The configured wiki root should contain:

- `raw/` - immutable converted source material
- `wiki/` - agent/human-maintained durable knowledge
- `site/` - generated output, if used
- `CLAUDE.md` and/or `AGENTS.md` - local operating schema

## Operating Model

1. Read `CLAUDE.md` or `AGENTS.md` at the start of any wiki operation.
2. Read `wiki/index.md`, `wiki/overview.md`, `wiki/hot.md`, and `wiki/MEMORY.md` before answering from the library.
3. Keep `raw/` immutable. Never edit converted session transcripts directly.
4. Write durable knowledge into `wiki/`, not into this skill directory.
5. Use wikilinks like `[[ConceptName]]` for cross-agent references.
6. Append operational notes to `wiki/log.md`.

## Common Commands

Run these from the integration project:

```bash
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "A durable conclusion or decision"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "starship dotfiles"
python3 -m pelib.cli feedback "This page needs clearer evidence links" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
python3 -m pelib.cli feedback-inbox
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run
```

## Workflow Hints

- For sync operations, prefer the `pel` wrapper if installed.
- For durable conclusions, use `capture` first; then use `inbox` and `promote`.
- Add `--confidence` on `capture` or `promote` when a claim is uncertain.
- Use `obsidian-import` for explicit paths instead of syncing a full personal vault by accident.
- If a fact is not in the wiki, say so and suggest what source to ingest.
