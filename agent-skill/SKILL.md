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

- Wiki root: `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki`
- Raw sources: `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki/raw`
- Human/agent-maintained wiki: `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki/wiki`
- Generated site: `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki/site`
- Agent schema files:
  - `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki/CLAUDE.md`
  - `/Users/fengguanghuai/Documents/Obsidian Vault/LLM Wiki/AGENTS.md`

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
cd /Users/fengguanghuai/Documents/Codex/2026-04-19-mac-2/workspace/projects/personal-execution-library
python3 -m pelib.cli sync --dry-run
python3 -m pelib.cli sync
python3 -m pelib.cli build
python3 -m pelib.cli serve
```

## When To Use

- The user asks what past AI conversations concluded.
- The user wants to ingest a conversation, note, article, or decision.
- The user wants an answer grounded in their own local wiki.
- The user wants an agent to reuse knowledge created by another agent.
- The user asks to update memory, project facts, or execution conventions.

## Workflow Hints

- For sync/build/serve, prefer the `pel` wrapper if installed.
- For deep edits, follow the wiki rules in `CLAUDE.md` and `AGENTS.md`.
- If a fact is not in the wiki, say so and suggest what source to ingest.
- Do not copy this wiki into agent-specific folders.
