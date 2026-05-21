# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A self-contained Python 3.11+ CLI (`pel`) for capturing, promoting, and querying a personal LLM wiki shared by multiple AI agents (Claude Code, Codex CLI, Gemini CLI). The wiki itself lives **outside** this repo at `wiki_root` (a user-owned Markdown vault). This repo only contains the tooling.

**Zero third-party dependencies.** Standard library only. `tomllib` (stdlib in 3.11+) handles config; `argparse` handles CLI; no PyYAML — there's a small custom frontmatter parser in `pelib/frontmatter.py`.

## Common Commands

```bash
# Run without install:
python3 -m pelib.cli status
python3 -m pelib.cli doctor
python3 -m pelib.cli init --wiki-root "../LLM-WIKI Vault" --title "X" --link-agents

# Editable install gives the `pel` short command:
pip install -e .

# Tests (stdlib unittest, all 23 currently pass):
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_inbox -v
python3 -m unittest tests.test_inbox.PromoteTests.test_promote_to_memory_marks_note
```

No linter or formatter is configured. Don't introduce one unless asked.

## Module Layout

`pelib/` is intentionally flat — one concern per module, no subpackages yet.

| Module | Concern |
|---|---|
| `config.py` | `Config` dataclass + `load_config()` reading `pelib.toml` via `tomllib` |
| `wiki.py` | Wiki skeleton dirs, seed templates, queryable-file resolution |
| `frontmatter.py` | Hand-rolled YAML-ish parser/renderer (string/int/float/bool/list[str] only — no nesting) |
| `log.py` | Append-only `wiki/log.md` writer |
| `markdown.py` | `slugify`, `title_slug` (CJK-preserving), `tokenize_query`, `score_match`, `best_snippet` |
| `skill.py` | Render `.pelib/agent-skill/SKILL.md` + symlink to `~/.codex/skills/` & `~/.claude/skills/` |
| `memory.py` | Append a Section to `wiki/MEMORY.md` |
| `inbox.py` | `capture`, `list_notes`, `find_matches`, `promote`, `promote_batch`, `_mark_promoted` |
| `query.py` | Full-text scoring across queryable files |
| `correct.py` | `record(page, message)` — appends to log only; user edits the page by hand |
| `cli.py` | argparse glue. Dispatches via `HANDLERS` dict |

## Important Module-Boundary Decisions

- **`correct.record`** does **not** modify the target page. It only appends a line to `wiki/log.md`. The user (or another agent) is expected to edit the page by hand. This is intentional — automatic page-editing for "corrections" was rejected as too magical for a single-user knowledge base.
- **`query.search`** only scans files listed by `wiki.queryable_files` (index/overview/hot/MEMORY at the top level, plus everything under `wiki/{concepts,entities,projects,syntheses,playbooks}/`). It deliberately skips `wiki/inbox/` because inbox notes are work-in-progress, not searchable knowledge.
- **`inbox.promote` slug rule**: `concept` / `entity` use `title_slug()` (TitleCase, CJK-preserving); `project` / `synthesis` use `slugify()` (kebab-case). Keep that asymmetry when touching slugging.
- **`promote_batch`** iterates open notes in filename order (timestamp prefix → chronological). If two `capture` calls happen within the same second, the second call's slug collision is **not** handled. Tests use `time.sleep(1.05)` between captures to avoid this.

## CLI Conventions

- The `pelib/cli.py` `HANDLERS` dict is the canonical command registry. To add a new command: add a subparser in `_build_parser`, write a `_cmd_<name>` function, register it in `HANDLERS`.
- `cli.PROJECT_ROOT` is set at module load from `__file__`. Tests monkey-patch it (`cli.PROJECT_ROOT = tmpdir`) for isolation.
- All commands print to stdout on success and stderr on error; never raise to argparse.
- Confidence values are floats in `[0.0, 1.0]`; `_check_confidence` returns the sentinel `_INVALID` on out-of-range and the handler returns 1.

## Wiki Schema (created by `init`)

```
<wiki_root>/
├── CLAUDE.md  AGENTS.md            # agent contracts (seeded once, then user-owned)
├── wiki/index.md  MEMORY.md  log.md
├── wiki/{inbox,concepts,entities,projects,syntheses,playbooks}/
├── raw/{articles,papers,notes,refs}/   # reserved for future `sync`
├── site/                                # reserved for static output
└── outputs/queries/                     # reserved for query exports
```

`init` is idempotent — it only creates missing dirs and seed files; pre-existing files are preserved.

## What's Intentionally NOT Here

- No `sync` command yet — adapter layer for `claude_code` / `codex_cli` / `gemini_cli` is on the roadmap but not implemented.
- No web viewer, no Obsidian plugin, no audit/feedback inbox. Those were in the earlier (pre-rewrite) version that vendored upstream code; they were dropped to keep the codebase legally clean and small.
- No third-party deps, no Node toolchain.

If you're about to add any of the above, confirm with the user first — they were deliberate omissions, not oversights.

## Config Notes

- `pelib.toml` is `.gitignore`d. Tests construct `Config` directly rather than reading the file.
- `Config.skill_dir` is always `<repo>/.pelib/agent-skill`. Rendered `SKILL.md` lives there and that directory is what gets symlinked from agent skill dirs. `.pelib/` is gitignored.
- `default_wiki_root(project_root)` returns `<project_root.parent>/LLM-WIKI Vault` — a sibling of the code repo, never inside it.
