from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pelib.adapters.codex_cli import CodexCliAdapter


SID = "019dab34-50a9-7370-8376-0a73de394625"


def _write_fixture(home: Path) -> Path:
    day = home / "sessions" / "2026" / "04" / "20"
    day.mkdir(parents=True)
    path = day / f"rollout-2026-04-20T22-03-45-{SID}.jsonl"
    events = [
        {"timestamp": "2026-04-20T14:04:00.741Z", "type": "session_meta", "payload": {
            "id": SID,
            "timestamp": "2026-04-20T14:03:45.708Z",
            "cwd": "/Users/foo/workspace/demo",
            "model_provider": "openai",
        }},
        {"timestamp": "2026-04-20T14:04:01Z", "type": "turn_context", "payload": {
            "turn_id": "t1", "cwd": "/Users/foo/workspace/demo", "model": "gpt-5.3-codex",
        }},
        {"timestamp": "2026-04-20T14:04:02Z", "type": "response_item", "payload": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "<environment_context>noise</environment_context>"}],
        }},
        {"timestamp": "2026-04-20T14:04:03Z", "type": "response_item", "payload": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "hello there"}],
        }},
        {"timestamp": "2026-04-20T14:04:04Z", "type": "response_item", "payload": {
            "type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "Hi, how can I help?"}],
        }},
        {"timestamp": "2026-04-20T14:04:05Z", "type": "response_item", "payload": {
            "type": "function_call",
            "name": "exec_command",
            "arguments": json.dumps({"cmd": "ls"}),
            "call_id": "call_1",
        }},
        {"timestamp": "2026-04-20T14:04:06Z", "type": "response_item", "payload": {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "file1\nfile2\n",
        }},
        {"timestamp": "2026-04-20T14:04:07Z", "type": "response_item", "payload": {
            "type": "message", "role": "developer",
            "content": [{"type": "input_text", "text": "system reminder, skip me"}],
        }},
        {"timestamp": "2026-04-20T14:04:08Z", "type": "event_msg", "payload": {"type": "token_count"}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


class CodexCliAdapterTests(unittest.TestCase):
    def test_discover_finds_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_fixture(home)
            adapter = CodexCliAdapter(home=home)
            sources = list(adapter.discover())
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].adapter, "codex_cli")

    def test_convert_renders_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_fixture(home)
            adapter = CodexCliAdapter(home=home)
            source = next(iter(adapter.discover()))
            converted = adapter.convert(source)
            assert converted is not None
            self.assertEqual(converted.frontmatter["adapter"], "codex_cli")
            self.assertEqual(converted.frontmatter["sessionId"], SID)
            self.assertEqual(converted.frontmatter["project"], "demo")
            self.assertEqual(converted.frontmatter["model"], "gpt-5.3-codex")
            self.assertTrue(converted.output_relative.startswith("raw/sessions/codex_cli/"))

            body = converted.body
            self.assertIn("hello there", body)
            self.assertIn("Hi, how can I help?", body)
            self.assertIn("🔧 **Tool use: `exec_command`**", body)
            self.assertIn("📤 **Tool result:**", body)
            self.assertIn("file1", body)
            # developer noise and env-context wrapper must be filtered
            self.assertNotIn("system reminder", body)
            self.assertNotIn("<environment_context>", body)


if __name__ == "__main__":
    unittest.main()
