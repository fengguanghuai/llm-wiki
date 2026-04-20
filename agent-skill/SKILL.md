---
name: personal-execution-library
description: >-
  Use this skill when the user asks to remember, ingest, query, update, audit,
  or reuse knowledge from the shared personal execution library. The library is
  one central LLM Wiki shared by Codex, Claude Code, and other local agents.
---

# Personal Execution Library

This is a thin shared skill. Do not create a new knowledge base for this agent.
Use the central wiki below.

## Central Wiki

- Wiki root: `/Users/fengguanghuai/Documents/LLM-WIKI Vault`
- Raw sources: `/Users/fengguanghuai/Documents/LLM-WIKI Vault/raw`
- Human/agent-maintained wiki: `/Users/fengguanghuai/Documents/LLM-WIKI Vault/wiki`
- Generated site: `/Users/fengguanghuai/Documents/LLM-WIKI Vault/site`
- Agent schema files:
  - `/Users/fengguanghuai/Documents/LLM-WIKI Vault/CLAUDE.md`
  - `/Users/fengguanghuai/Documents/LLM-WIKI Vault/AGENTS.md`

## Operating Model

Use the central wiki as the durable memory and execution library:

1. Read `CLAUDE.md` or `AGENTS.md` at the start of any wiki operation.
2. Read `wiki/index.md`, `wiki/overview.md`, `wiki/hot.md`, and `wiki/MEMORY.md` before answering from the library.
3. Keep `raw/` immutable. Never edit converted session transcripts directly.
4. Write durable knowledge into `wiki/`, not into this skill directory.
5. Use wikilinks like `[[ConceptName]]` for cross-agent references.
6. Append operational notes to `wiki/log.md`.

## Common Commands

Run these from the integration project:

```bash
cd /Users/fengguanghuai/workspace/personal-execution-library
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli capture "A durable conclusion or decision"
python3 -m pelib.cli inbox
python3 -m pelib.cli promote <inbox-note> --to memory
python3 -m pelib.cli feedback "This page needs clearer evidence links" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
python3 -m pelib.cli feedback-inbox
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "starship dotfiles"
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run
python3 -m pelib.cli build
python3 -m pelib.cli serve
```

## When To Use

- The user asks what past AI conversations concluded.
- The user wants to ingest a conversation, note, article, or decision.
- The user wants an answer grounded in their own local wiki.
- The user wants an agent to reuse knowledge created by another agent.
- The user asks to update memory, project facts, or execution conventions.
- The user says "remember this", "this is the conclusion", or "use this later".

## Workflow Hints

- For sync/build/serve, prefer the `pel` wrapper if installed.
- For deep edits, follow the wiki rules in `CLAUDE.md` and `AGENTS.md`.
- For durable conclusions, use `capture` first; then use `inbox` and `promote`
  to move reviewed notes into `MEMORY.md`, `concepts/`, `entities/`, or `projects/`.
- Add `--confidence` on `capture`/`promote` when a claim is uncertain.
- Capture review notes from web/Obsidian via `feedback` and triage with `feedback-inbox`.
- For larger inbox cleanup, use `promote-batch` with `--dry-run` first.
- For quick discovery before answering, use `query` to rank candidate pages.
- For Obsidian notes, use `obsidian-import` to whitelist explicit paths instead of syncing the whole vault.
- Do not promote uncertain or speculative claims without marking uncertainty.
- If a fact is not in the wiki, say so and suggest what source to ingest.
- Do not copy this wiki into agent-specific folders.
