"""Tests voor scripts/kb-mcp.py - recall-tool core (zonder mcp-pakket/model)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("kb_mcp", str(SCRIPTS_DIR / "kb-mcp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbMcpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mcp-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load()
        if getattr(self.m, "kb_recall", None) is None:
            self.skipTest("kb_recall niet beschikbaar (sqlite_vec ontbreekt?)")
        import _embeddings as emb
        self._orig_embed = emb.embed
        emb.embed = lambda text, timeout=30.0: [0.1, 0.2, 0.3]
        self.emb = emb
        self._orig_recall = self.m.kb_recall.recall_hits
        self.m.kb_recall.recall_hits = lambda *a, **k: [
            {"path": "/v/09-memory/x.md", "layer": "memory", "title": "Oude bug",
             "created": "2026-06-01", "score": 0.9, "snippet": "token expiry < ipv <="}]

    def tearDown(self):
        import shutil
        self.emb.embed = self._orig_embed
        self.m.kb_recall.recall_hits = self._orig_recall
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recall_tool_formats_hits(self):
        out = self.m.recall_tool("token expiry bug")
        self.assertIn("Oude bug", out)
        self.assertIn("geheugen", out)

    def test_recall_tool_empty_query(self):
        self.assertEqual(self.m.recall_tool("").strip(), "")

    def test_recall_tool_no_hits(self):
        self.m.kb_recall.recall_hits = lambda *a, **k: []
        out = self.m.recall_tool("iets")
        self.assertIn("geen", out.lower())

    def test_recall_tool_embed_fail_is_soft(self):
        self.emb.embed = lambda *a, **k: None
        self.assertIn("geen", self.m.recall_tool("iets").lower())

    def test_build_server_none_without_mcp(self):
        # in deze omgeving is mcp niet geinstalleerd -> build_server geeft None
        if self.m.MCPServer is None:
            self.assertIsNone(self.m.build_server())
        else:
            self.assertIsNotNone(self.m.build_server())


class KbMcpTemporalToolTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.orig = self.m.activity

        class FakeActivity:
            @staticmethod
            def what_did_i_do(*_a, **_k):
                return {"ok": True, "mode": "what_did_i_do", "events": [{"id": "e1", "source_ref": "x#L1"}]}

            @staticmethod
            def timeline(*_a, **_k):
                return {"ok": True, "mode": "timeline", "events": []}

            @staticmethod
            def weeklog(*_a, **_k):
                return {"ok": True, "mode": "weeklog", "rollup": {"event_count": 0}, "events": []}

            @staticmethod
            def topic_timeline(*_a, **_k):
                return {"ok": True, "mode": "topic_timeline", "events": []}

        self.m.activity = FakeActivity

    def tearDown(self):
        self.m.activity = self.orig

    def test_temporal_tool_wrappers_return_json(self):
        out = json.loads(self.m.what_did_i_do_tool("2026-07-03"))
        self.assertTrue(out["ok"])
        self.assertEqual(out["events"][0]["source_ref"], "x#L1")
        self.assertEqual(json.loads(self.m.timeline_tool("vorige week"))["mode"], "timeline")
        self.assertEqual(json.loads(self.m.weeklog_tool())["mode"], "weeklog")
        self.assertEqual(json.loads(self.m.topic_timeline_tool("Codex MCP"))["mode"], "topic_timeline")


if __name__ == "__main__":
    unittest.main()
