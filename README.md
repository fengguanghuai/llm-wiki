# Personal Execution Library

This project is a thin integration layer over two upstream ideas:

- `Pratiyush/llm-wiki`: session sync, static-site generation, adapters, and wiki outputs.
- `lewislulu/llm-wiki-skill`: agent workflow rules for ingest, query, lint, audit, and feedback.

The goal is one central local wiki shared by every agent, not one duplicated wiki per agent.

## Vendored Engine

This repository now vendors both upstream dependencies under `vendor/`:

- `vendor/llm-wiki`
- `vendor/llm-wiki-skill`

`pel` uses the vendored `llm-wiki` engine by default, so users can run this
project without separately cloning upstream repos.

For repository size, this project keeps only the runtime-needed subset of
`llm-wiki` (not upstream docs/tests/tooling). `llm-wiki-skill` is optional at
runtime.

## Current Center

The central wiki is:

```text
/Users/fengguanghuai/Documents/LLM-WIKI Vault
```

This integration project wraps the AI vault and installs a shared thin skill that points agents back to it.

The personal Obsidian vault remains separate at:

```text
/Users/fengguanghuai/Documents/Obsidian Vault
```

Do not use the personal vault as the active AI knowledge center. The AI vault
contains only the wiki-facing parts: `CLAUDE.md`, `AGENTS.md`, `raw/`, `wiki/`,
and generated `site/`.

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
python3 -m pelib.cli feedback "This page needs clearer evidence links" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
python3 -m pelib.cli feedback-inbox
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli query "starship dotfiles"
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run
python3 -m pelib.cli skill-web-build --install
python3 -m pelib.cli skill-web-serve --port 4175
python3 -m pelib.cli skill-obsidian-build --install
python3 -m pelib.cli skill-obsidian-link "/path/to/your/Obsidian vault"
python3 -m pelib.cli build
python3 -m pelib.cli serve --port 8765
python3 -m pelib.cli link-agents
python3 -m unittest discover -s tests -v
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
pel feedback "This page needs clearer evidence links" --from obsidian --target "wiki/projects/dotfiles.md" --verdict needs-work
pel feedback-inbox
pel promote-batch --to memory --dry-run
pel query "starship dotfiles"
pel obsidian-import "daily-logs/2026-03-25" --dry-run
pel skill-web-build --install
pel skill-web-serve --port 4175
pel skill-obsidian-build --install
pel skill-obsidian-link "/path/to/your/Obsidian vault"
pel build
pel serve
pel link-agents
```

`pel sync` intentionally runs only `claude_code`, `codex_cli`, and `copilot-chat`
by default. The vendored upstream `obsidian` adapter can ingest the entire vault,
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
python3 -m pelib.cli capture "Likely root cause is stale cache" --confidence 0.55
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
python3 -m pelib.cli promote "cache" --to memory --confidence 0.60
```

Promotion keeps the original inbox note and marks it as `status: promoted`
with a `promoted_to` field, so the knowledge remains traceable.

Batch promote open notes:

```bash
python3 -m pelib.cli promote-batch --to memory --dry-run
python3 -m pelib.cli promote-batch --to memory
python3 -m pelib.cli promote-batch --to concept --append --limit 10
```

Search for candidate pages before answering:

```bash
python3 -m pelib.cli query "starship prompt"
python3 -m pelib.cli query "dotfiles backup strategy" --limit 20
```

Capture web/Obsidian feedback in audit format:

```bash
python3 -m pelib.cli feedback "Needs stronger source links in conclusions." --from web --target "wiki/MEMORY.md" --verdict needs-work
python3 -m pelib.cli feedback "Terminology is inconsistent across pages." --from obsidian --target "wiki/projects/llm-wiki.md" --verdict question --tag wording
python3 -m pelib.cli feedback-inbox
```

Whitelist import from Obsidian without scanning the whole vault:

```bash
# one folder
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25" --dry-run

# multiple explicit files/folders
python3 -m pelib.cli obsidian-import "test-2026-03-25.md" "daily-logs/2026-03-27" --dry-run

# apply for real
python3 -m pelib.cli obsidian-import "daily-logs/2026-03-25"
```

Run the vendored `llm-wiki-skill` web viewer via `pel`:

```bash
# one-time install + build
python3 -m pelib.cli skill-web-build --install

# start viewer against central wiki root (default wiki_root)
python3 -m pelib.cli skill-web-serve --port 4175

# or point to a custom wiki root
python3 -m pelib.cli skill-web-serve --wiki "/path/to/wiki-root" --port 4175
```

Build/link the vendored Obsidian audit plugin via `pel`:

```bash
# one-time install + build
python3 -m pelib.cli skill-obsidian-build --install

# link into a vault (same as plugin's npm run link)
python3 -m pelib.cli skill-obsidian-link "/path/to/your/Obsidian vault"
```

## What This Does Not Do Yet

- It does not rewrite the upstream `llmwiki` engine.
- It does not store secrets or agent tokens.
- It does not merge multiple Obsidian vaults.
- It runs vendored upstream `Pratiyush/llm-wiki` code while overriding
  `REPO_ROOT` to point at your central Obsidian wiki.

## Suggested Next Milestones

1. Add feedback-to-promotion helpers (e.g. convert one feedback note directly into a capture/promote draft).
2. Expand tests with end-to-end CLI invocation coverage for `feedback`, `query`, and `promote-batch`.
3. Add configurable verdict taxonomy for different review workflows.
