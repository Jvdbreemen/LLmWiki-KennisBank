"""Tests voor scripts/kb-presearch.py - PreToolUse presearch-hook. Geen echt
model: we monkeypatchen emb.embed + kb_recall.recall_hits. Draait de hook als
functie (via importlib) met een gefabriceerde hook-JSON."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("kb_presearch", str(SCRIPTS_DIR / "kb-presearch.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class KbPresearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-pre-"))
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

    def _run(self, payload, settings=None):
        if settings is not None:
            (self.vault / "kennisbank-settings.json").write_text(json.dumps(settings), encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.m.main(stdin_text=json.dumps(payload))
        return buf.getvalue()

    def test_websearch_injects_context(self):
        out = self._run({"tool_name": "WebSearch", "tool_input": {"query": "token expiry bug"}})
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "defer")
        self.assertIn("Oude bug", data["hookSpecificOutput"]["additionalContext"])

    def test_non_search_tool_no_output(self):
        self.assertEqual(self._run({"tool_name": "Bash", "tool_input": {"command": "ls"}}).strip(), "")

    def test_memory_recall_off_no_output(self):
        out = self._run({"tool_name": "WebSearch", "tool_input": {"query": "x bug here"}},
                        settings={"memory_recall": False})
        self.assertEqual(out.strip(), "")

    def test_no_hits_no_output(self):
        self.m.kb_recall.recall_hits = lambda *a, **k: []
        self.assertEqual(self._run({"tool_name": "WebSearch", "tool_input": {"query": "iets"}}).strip(), "")

    def test_webfetch_uses_url(self):
        out = self._run({"tool_name": "WebFetch", "tool_input": {"url": "https://example.com/x"}})
        self.assertIn("additionalContext", out)

    def test_garbage_input_failopen(self):
        self.assertEqual(self._run({}).strip(), "")  # geen tool_name -> stil

    def test_bad_json_failopen(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.m.main(stdin_text="not-json{{")
        self.assertEqual(buf.getvalue().strip(), "")

    def test_embed_exception_failopen(self):
        self.emb.embed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ollama down"))
        out = self._run({"tool_name": "WebSearch", "tool_input": {"query": "iets relevants"}})
        self.assertEqual(out.strip(), "")


if __name__ == "__main__":
    unittest.main()
