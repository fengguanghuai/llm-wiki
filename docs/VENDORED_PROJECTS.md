# Bundled Upstream Projects

This repository carries two upstream-derived code areas:

- `llmwiki/` — bundled in-repo conversion engine
- `llm-wiki-skill/` — bundled optional tooling

This file explains what each one is for, what this project uses, and what is optional.

## 1. `llmwiki/`

Origin:

- Upstream project: `Pratiyush/llm-wiki`
- Local role: conversion-focused subset

What this project uses:

- `pel sync` delegates to `llmwiki sync`.
- `pel obsidian-import` calls `llmwiki.convert.convert_all(adapters=["obsidian"])`.
- `pel llmwiki -- ...` exposes the slim bundled `llmwiki` CLI.

Current scope:

- Kept: conversion engine, adapter registry, session/document adapters, quarantine helpers.
- Removed from this bundled subset: most static-site, graph, lint, watch, scheduling, and visualization surfaces.

Adapter policy:

- Default in `pel`: `claude_code`, `codex_cli`, `copilot-chat`
- Opt-in: `obsidian`
- Preserved but not default: other bundled adapters

## 2. `llm-wiki-skill/`

Origin:

- Upstream project: `lewislulu/llm-wiki-skill`
- Local role: optional skill/web/plugin tooling

What this project uses:

- `pel skill-web-build`
- `pel skill-web-serve`
- `pel skill-obsidian-build`
- `pel skill-obsidian-link`

Subdirectories:

- `audit-shared/` — shared TypeScript audit schemas and serialization helpers
- `web/` — web viewer
- `plugins/obsidian-audit/` — Obsidian audit plugin
- `llm-wiki/` — skill instructions and references

Important notes:

- `llm-wiki-skill` is not required for core conversion flows.
- If Node.js or npm is unavailable, `pel sync`, `pel query`, `pel capture`, and related Python flows still work.
- Do not commit `node_modules/`, `dist/`, or TypeScript build info.

## Open Source Maintenance Notes

- Keep upstream license and attribution files in `third_party_licenses/`.
- Document any substantial local changes in this file.
- Prefer reducing optional surfaces before changing adapter behavior.
