from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pelib.adapters.gemini_cli import GeminiCliAdapter


SID = "b5678815-f6d6-4128-b884-74b206033596"


def _write_json_fixture(tmp_dir: Path) -> Path:
    chats = tmp_dir / "demo" / "chats"
    chats.mkdir(parents=True)
    path = chats / f"session-2026-04-25T03-32-{SID[:8]}.json"
    data = {
        "sessionId": SID,
        "projectHash": "abcdef",
        "startTime": "2026-04-25T03:32:33.021Z",
        "lastUpdated": "2026-04-25T05:28:23.421Z",
        "kind": "main",
        "summary": "了解 Gemini 模型的使用范围",
        "messages": [
            {"id": "m1", "timestamp": "2026-04-25T03:45:58.671Z", "type": "user",
             "content": [{"text": "你好,你现在是什么模型"}]},
            {"id": "m2", "timestamp": "2026-04-25T03:46:02.605Z", "type": "gemini",
             "content": "我是 Gemini CLI。",
             "model": "gemini-2.5-pro",
             "thoughts": [{"subject": "Identity", "description": "User asked who I am."}]},
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _write_jsonl_fixture(tmp_dir: Path) -> Path:
    chats = tmp_dir / "demo" / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    path = chats / f"session-2026-05-16T16-36-{SID[:8]}.jsonl"
    lines = [
        {"sessionId": SID, "projectHash": "xyz", "startTime": "2026-05-16T16:36:41.597Z",
         "lastUpdated": "2026-05-16T16:36:41.597Z", "kind": "main"},
        {"id": "m1", "timestamp": "2026-05-16T16:36:41Z", "type": "user",
         "content": [{"text": "List my projects"}]},
        {"$set": {"some": "mutation"}},
        {"id": "m2", "timestamp": "2026-05-16T16:36:42Z", "type": "gemini",
         "model": "gemini-2.5-flash",
         "content": "Here are your projects.",
         "toolCalls": [{"name": "list_projects", "arguments": {"limit": 5}, "output": "p1\np2"}]},
    ]
    path.write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
    return path


class GeminiCliAdapterTests(unittest.TestCase):
    def test_discover_finds_both_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_json_fixture(tmp_dir)
            _write_jsonl_fixture(tmp_dir)
            adapter = GeminiCliAdapter(tmp_dir=tmp_dir)
            sources = list(adapter.discover())
            self.assertEqual(len(sources), 2)
            suffixes = sorted(s.path.suffix for s in sources)
            self.assertEqual(suffixes, [".json", ".jsonl"])

    def test_convert_json_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_json_fixture(tmp_dir)
            adapter = GeminiCliAdapter(tmp_dir=tmp_dir)
            source = next(iter(adapter.discover()))
            converted = adapter.convert(source)
            assert converted is not None
            self.assertEqual(converted.frontmatter["adapter"], "gemini_cli")
            self.assertEqual(converted.frontmatter["sessionId"], SID)
            self.assertEqual(converted.frontmatter["project"], "demo")
            self.assertEqual(converted.frontmatter["model"], "gemini-2.5-pro")
            self.assertIn("了解 Gemini", converted.frontmatter["title"])
            self.assertIn("你好,你现在是什么模型", converted.body)
            self.assertIn("我是 Gemini CLI。", converted.body)
            self.assertIn("<details><summary>thinking</summary>", converted.body)

    def test_convert_jsonl_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _write_jsonl_fixture(tmp_dir)
            adapter = GeminiCliAdapter(tmp_dir=tmp_dir)
            source = next(iter(adapter.discover()))
            converted = adapter.convert(source)
            assert converted is not None
            self.assertEqual(converted.frontmatter["model"], "gemini-2.5-flash")
            body = converted.body
            self.assertIn("List my projects", body)
            self.assertIn("Here are your projects.", body)
            self.assertIn("🔧 **Tool use: `list_projects`**", body)
            self.assertIn("📤 **Tool result:**", body)


if __name__ == "__main__":
    unittest.main()
