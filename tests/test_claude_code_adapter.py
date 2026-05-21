from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pelib.adapters.claude_code import ClaudeCodeAdapter


def _write_fixture(root: Path) -> Path:
    project = root / "projects" / "-Users-someone-workspace-demo"
    project.mkdir(parents=True)
    path = project / "abc12345-aaaa-bbbb-cccc-000000000000.jsonl"
    lines = [
        {"type": "permission-mode", "permissionMode": "default",
         "sessionId": "abc12345-aaaa-bbbb-cccc-000000000000"},
        {"type": "user", "message": {"role": "user", "content": "hi there"},
         "timestamp": "2026-05-19T16:26:38.000Z",
         "cwd": "/Users/someone/workspace/demo",
         "sessionId": "abc12345-aaaa-bbbb-cccc-000000000000"},
        {"type": "assistant", "message": {
            "role": "assistant",
            "model": "claude-haiku-4-5",
            "content": [
                {"type": "text", "text": "Hello!"},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            ],
        }, "timestamp": "2026-05-19T16:26:40.000Z",
         "sessionId": "abc12345-aaaa-bbbb-cccc-000000000000"},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "file1\nfile2\n"},
        ]}, "timestamp": "2026-05-19T16:26:41.000Z",
         "sessionId": "abc12345-aaaa-bbbb-cccc-000000000000"},
        {"type": "user", "message": {"role": "user",
            "content": "<local-command-caveat>noise</local-command-caveat>"},
         "isMeta": True,
         "timestamp": "2026-05-19T16:26:42.000Z",
         "sessionId": "abc12345-aaaa-bbbb-cccc-000000000000"},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


class ClaudeCodeAdapterTests(unittest.TestCase):
    def test_discover_finds_jsonl_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root)
            adapter = ClaudeCodeAdapter(roots=[root])
            sources = list(adapter.discover())
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].adapter, "claude_code")
            self.assertTrue(str(sources[0].path).endswith(".jsonl"))

    def test_convert_renders_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fixture(root)
            adapter = ClaudeCodeAdapter(roots=[root])
            source = next(iter(adapter.discover()))
            converted = adapter.convert(source)
            assert converted is not None
            self.assertEqual(converted.frontmatter["adapter"], "claude_code")
            self.assertEqual(converted.frontmatter["project"], "demo")
            self.assertEqual(converted.frontmatter["model"], "claude-haiku-4-5")
            self.assertEqual(converted.frontmatter["date"], "2026-05-19")
            self.assertTrue(converted.output_relative.startswith("raw/sessions/claude_code/"))
            self.assertIn("2026-05-19-demo-abc12345", converted.output_relative)

            body = converted.body
            self.assertIn("# Session: abc12345 — 2026-05-19", body)
            self.assertIn("### Turn 1 — User", body)
            self.assertIn("hi there", body)
            self.assertIn("### Turn 2 — Assistant", body)
            self.assertIn("Hello!", body)
            self.assertIn("🔧 **Tool use: `Bash`**", body)
            self.assertIn("### Turn 3 — User", body)
            self.assertIn("📤 **Tool result:**", body)
            # The local-command-caveat noise event must be filtered out.
            self.assertNotIn("local-command-caveat", body)

    def test_empty_or_malformed_jsonl_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projects" / "empty"
            project.mkdir(parents=True)
            empty = project / "00000000-0000-0000-0000-000000000000.jsonl"
            empty.write_text("", encoding="utf-8")
            adapter = ClaudeCodeAdapter(roots=[root])
            source = next(iter(adapter.discover()))
            self.assertIsNone(adapter.convert(source))


if __name__ == "__main__":
    unittest.main()
