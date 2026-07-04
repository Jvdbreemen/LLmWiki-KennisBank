"""Tests voor kb-ask.py — de manuele export-bridge (TASK-22).

Ollama-vrij: we injecteren hits via kb_recall.recall_hits-monkeypatch en emb.embed.
Bewijst de wikkel-vorm (context boven, vraag onder) + fail-soft bij geen hits."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("kb_ask", str(SCRIPTS_DIR / "kb-ask.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_format_hits_tags_layer(self):
        hits = [
            {"layer": "memory", "path": "/v/09-memory/a.md", "title": "Feit A",
             "snippet": "iets\nmet newline"},
            {"layer": "wiki", "path": "/v/02-wiki/b.md", "title": "Artikel B",
             "snippet": "wiki-inhoud"},
        ]
        out = self.m.format_hits(hits)
        self.assertIn("[geheugen] Feit A:", out)
        self.assertIn("[wiki] Artikel B:", out)
        self.assertNotIn("\nmet newline", out)  # newline in snippet platgeslagen

    def test_gather_failsoft_without_recall(self):
        self.m.kb_recall = None
        self.assertEqual(self.m.gather("iets", 5), [])

    def test_gather_uses_recall_hits(self):
        seen = {}

        class FakeEmb:
            @staticmethod
            def embed(q, timeout=None):
                return [0.1, 0.2]

        class FakeRecall:
            @staticmethod
            def recall_hits(qvec, query_text="", k=3, layers=None):
                seen["k"] = k
                seen["layers"] = layers
                return [{"layer": "wiki", "path": "/v/02-wiki/x.md",
                         "title": "X", "snippet": "y"}]

        # save/restore de _embeddings-module zodat deze stub niet naar andere
        # testmodules lekt (test-isolatie via teardown).
        saved_emb = sys.modules.get("_embeddings")
        saved_recall = self.m.kb_recall
        sys.modules["_embeddings"] = FakeEmb
        self.m.kb_recall = FakeRecall
        try:
            hits = self.m.gather("vraag", 7)
        finally:
            if saved_emb is None:
                sys.modules.pop("_embeddings", None)
            else:
                sys.modules["_embeddings"] = saved_emb
            self.m.kb_recall = saved_recall
        self.assertEqual(len(hits), 1)
        self.assertEqual(seen["k"], 7)
        self.assertEqual(seen["layers"], ("wiki", "memory"))


if __name__ == "__main__":
    unittest.main()
