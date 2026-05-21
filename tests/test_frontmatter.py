from __future__ import annotations

import unittest

from pelib import frontmatter


class FrontmatterTests(unittest.TestCase):
    def test_parse_no_frontmatter(self) -> None:
        meta, body = frontmatter.parse("hello world")
        self.assertEqual(meta, {})
        self.assertEqual(body, "hello world")

    def test_parse_basic(self) -> None:
        text = '---\ntitle: "Hello"\nstatus: open\n---\n\nbody here\n'
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta["title"], "Hello")
        self.assertEqual(meta["status"], "open")
        self.assertEqual(body, "\nbody here\n")

    def test_parse_list(self) -> None:
        meta, _ = frontmatter.parse('---\ntags: ["a", "b", "c"]\n---\n')
        self.assertEqual(meta["tags"], ["a", "b", "c"])

    def test_parse_bool_and_number(self) -> None:
        meta, _ = frontmatter.parse(
            "---\nflag: true\nnum: 42\nf: 0.5\n---\n"
        )
        self.assertIs(meta["flag"], True)
        self.assertEqual(meta["num"], 42)
        self.assertEqual(meta["f"], 0.5)

    def test_round_trip_preserves_colon_in_value(self) -> None:
        original = {"title": "Hello: world", "tags": ["a", "b"], "status": "open"}
        rendered = frontmatter.render(original)
        meta, _ = frontmatter.parse(f"---\n{rendered}\n---\n")
        self.assertEqual(meta["title"], "Hello: world")
        self.assertEqual(meta["tags"], ["a", "b"])
        self.assertEqual(meta["status"], "open")

    def test_round_trip_empty_string(self) -> None:
        rendered = frontmatter.render({"title": ""})
        meta, _ = frontmatter.parse(f"---\n{rendered}\n---\n")
        self.assertEqual(meta["title"], "")


if __name__ == "__main__":
    unittest.main()
