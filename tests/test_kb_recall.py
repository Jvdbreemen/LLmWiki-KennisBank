"""Tests voor scripts/kb-recall.py - geheugen-recall over kb-index.db.

Bouwt een echte kb-index.db met fake vectoren (geen Ollama). Vault naar temp.
kb-recall heeft een hyphen -> via importlib laden.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402

DIM = 4


def _load_kb_recall():
    spec = importlib.util.spec_from_file_location("kb_recall", str(SCRIPTS_DIR / "kb-recall.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class KbRecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rec-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # bouw een index met 1 memory + 1 wiki, embed_id 'ollama:test'
        conn = _kbindex.connect()  # schrijft naar <vault>/.claude/kb-index.db
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")
        _kbindex.upsert(conn, path=str(self.vault / "09-memory" / "m1.md"),
                        layer="memory", status="current", body="hook gedreven retrieval bug",
                        vector=[0.1, 0.2, 0.3, 0.4], file_hash="h1", title="M1", created="2026-06-01")
        _kbindex.upsert(conn, path=str(self.vault / "02-wiki" / "w1.md"),
                        layer="wiki", status="current", body="wiki artikel",
                        vector=[0.9, 0.8, 0.7, 0.6], file_hash="h2", title="W1", created="2026-06-02")
        conn.close()
        self.kb = _load_kb_recall()
        # forceer actieve embed_id zodat happy-path niet mismatcht
        import _embeddings as emb
        self._orig_eid = emb.embed_id
        emb.embed_id = lambda: "ollama:test"

    def tearDown(self):
        import _embeddings as emb
        emb.embed_id = self._orig_eid
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_memory_hits_returns_only_memory_layer(self):
        hits = self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], query_text="bug", k=5)
        self.assertTrue(hits)
        self.assertTrue(all(Path(h["path"]).name == "m1.md" for h in hits))
        self.assertIn("snippet", hits[0])
        self.assertIn("title", hits[0])

    def test_embed_id_mismatch_returns_empty(self):
        # actieve embed_id != index embed_id -> geen resultaten
        import _embeddings as emb
        orig = emb.embed_id
        emb.embed_id = lambda: "ollama:ander-model"
        try:
            self.assertEqual(self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], k=5), [])
        finally:
            emb.embed_id = orig

    def test_missing_index_returns_empty(self):
        (self.vault / ".claude" / "kb-index.db").unlink()
        self.assertEqual(self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], k=5), [])


if __name__ == "__main__":
    unittest.main()
