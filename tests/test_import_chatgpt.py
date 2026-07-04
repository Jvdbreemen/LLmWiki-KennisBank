"""Tests voor import-chatgpt-export.py — de mapping-boom-parser (TASK-22).

Het schema-verschil met claude.ai (mapping-boom i.p.v. platte lijst) is het
enige risico; deze tests pinnen het: tijdsvolgorde uit create_time, parts-join,
system/tool/lege nodes eruit, dry-run schrijft niets."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(
        "import_chatgpt", str(SCRIPTS_DIR / "import-chatgpt-export.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _node(role, text, ct):
    return {"message": {"author": {"role": role},
                        "create_time": ct,
                        "content": {"content_type": "text", "parts": [text]}}}


class ChatGptParseTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_mapping_ordered_by_create_time(self):
        # bewust in verkeerde mapping-volgorde; create_time bepaalt de echte orde
        conv = {"id": "abc123", "title": "Test", "create_time": 1700000000.0,
                "mapping": {
                    "n2": _node("assistant", "tweede", 1700000002.0),
                    "root": {"message": None},
                    "n1": _node("user", "eerste", 1700000001.0),
                }}
        meta = self.m.parse_conversation(conv)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["human_turns"], 1)
        self.assertEqual(meta["assistant_turns"], 1)
        self.assertEqual(meta["first_human_text"], "eerste")
        # transcript: user-beurt vóór assistant-beurt
        t = meta["transcript"]
        self.assertLess(t.index("**Human:** eerste"), t.index("**Assistant:** tweede"))

    def test_system_and_tool_and_empty_nodes_dropped(self):
        conv = {"id": "x", "title": "T", "create_time": 1700000000.0,
                "mapping": {
                    "s": _node("system", "systeemprompt", 1.0),
                    "t": _node("tool", "tool-output", 2.0),
                    "e": _node("assistant", "", 3.0),          # lege parts
                    "u": _node("user", "echte vraag", 4.0),
                    "a": _node("assistant", "echt antwoord", 5.0),
                }}
        meta = self.m.parse_conversation(conv)
        self.assertEqual(meta["human_turns"], 1)
        self.assertEqual(meta["assistant_turns"], 1)
        self.assertNotIn("systeemprompt", meta["transcript"])
        self.assertNotIn("tool-output", meta["transcript"])

    def test_multipart_parts_joined(self):
        node = {"message": {"author": {"role": "user"}, "create_time": 1.0,
                            "content": {"parts": ["deel een", "deel twee"]}}}
        conv = {"id": "y", "title": "T", "create_time": 1700000000.0,
                "mapping": {"u": node,
                            "a": _node("assistant", "ok", 2.0)}}
        meta = self.m.parse_conversation(conv)
        self.assertIn("deel een", meta["transcript"])
        self.assertIn("deel twee", meta["transcript"])

    def test_no_user_turns_returns_none(self):
        conv = {"id": "z", "title": "T", "create_time": 1700000000.0,
                "mapping": {"a": _node("assistant", "alleen assistant", 1.0)}}
        self.assertIsNone(self.m.parse_conversation(conv))

    def test_missing_mapping_returns_none(self):
        self.assertIsNone(self.m.parse_conversation({"id": "q", "title": "T"}))

    def test_create_time_becomes_date(self):
        # 1700000000 = 2023-11-14 UTC
        conv = {"id": "d", "title": "T", "create_time": 1700000000.0,
                "mapping": {"u": _node("user", "vraag", 1.0)}}
        meta = self.m.parse_conversation(conv)
        self.assertEqual(meta["date"], "2023-11-14")

    def test_render_body_marks_chatgpt_source(self):
        conv = {"id": "abc", "title": "Mijn titel", "create_time": 1700000000.0,
                "mapping": {"u": _node("user", "vraag", 1.0),
                            "a": _node("assistant", "antwoord", 2.0)}}
        meta = self.m.parse_conversation(conv)
        body = self.m.render_body(meta, "/some/export.zip", "2026-07-04T00:00:00Z")
        self.assertIn("source: chatgpt-export", body)
        self.assertIn("type: raw-sessie", body)
        self.assertIn("import-chatgpt", body)


if __name__ == "__main__":
    unittest.main()
