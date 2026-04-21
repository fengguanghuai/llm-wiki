# Contributing

Thanks for helping improve Personal Execution Library.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp pelib.example.toml pelib.toml
```

Edit `pelib.toml` to point at a local test wiki root.

## Checks

Run the Python test suite:

```bash
python3 -m unittest discover -s tests -v
```

If you touch optional `llm-wiki-skill` web or plugin code, also run the relevant npm build in that subproject.

## Hygiene

- Do not commit personal wiki contents, local config, virtual environments, `node_modules`, or generated build output.
- Keep user-specific paths out of committed files.
- Preserve third-party attribution under `third_party_licenses/`.
