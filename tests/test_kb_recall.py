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

# Vaste body-tekst voor de live m1.md (gebruikt in snippet-assertie)
_M1_BODY = "hook gedreven retrieval bug"
_M1_MD = (
    '---\ntitle: "M1"\ntype: memory\nstatus: current\n'
    'evidence_basis: cc-sessie\nsource_session: ""\n'
    "created: 2026-06-01\nupdated: 2026-06-01\ntags: []\n---\n\n"
    + _M1_BODY + "\n"
)


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
                        layer="memory", status="current", body=_M1_BODY,
                        vector=[0.1, 0.2, 0.3, 0.4], file_hash="h1", title="M1", created="2026-06-01")
        _kbindex.upsert(conn, path=str(self.vault / "02-wiki" / "w1.md"),
                        layer="wiki", status="current", body="wiki artikel",
                        vector=[0.9, 0.8, 0.7, 0.6], file_hash="h2", title="W1", created="2026-06-02")
        conn.close()
        # schrijf ook het live bestand zodat read_status de echte status kan lezen
        # (MINOR 4: live bestand met echte body voor snippet-assertie)
        mem_dir = self.vault / "09-memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "m1.md").write_text(_M1_MD, encoding="utf-8")
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
        # MINOR 4: snippet bevat echte body-tekst uit het live bestand
        self.assertIn(_M1_BODY, hits[0]["snippet"])

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

    def test_stale_index_retracted_not_recalled(self):
        """Regressietest IMPORTANT 1: stale index dient geen ingetrokken geheugen op.

        Index zegt status=current (verouderd); live bestand zegt status=retracted.
        memory_hits moet het resultaat weggooien na live-validatie.
        RED vóór de fix in kb-recall.py, GREEN daarna.
        """
        retracted_md = (
            '---\ntitle: "M1"\ntype: memory\nstatus: retracted\n'
            'evidence_basis: cc-sessie\nsource_session: ""\n'
            "created: 2026-06-01\nupdated: 2026-06-01\ntags: []\n---\n\n"
            "Dit geheugen is ingetrokken.\n"
        )
        (self.vault / "09-memory" / "m1.md").write_text(retracted_md, encoding="utf-8")
        hits = self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], query_text="bug", k=5)
        hit_paths = [h["path"] for h in hits]
        self.assertNotIn(
            str(self.vault / "09-memory" / "m1.md"), hit_paths,
            "retracted memory werd teruggegeven via stale index (IMPORTANT 1 regressie)",
        )

    def test_recall_hits_returns_both_layers(self):
        hits = self.kb.recall_hits([0.1, 0.2, 0.3, 0.4], query_text="bug wiki",
                                   k=5, layers=("wiki", "memory"))
        layers = {h["layer"] for h in hits}
        self.assertIn("memory", layers)
        self.assertIn("wiki", layers)
        self.assertTrue(all("layer" in h for h in hits))

    def test_recall_hits_wiki_not_live_rechecked(self):
        # w1.md staat NIET op disk als geldige memory; toch moet de wiki-hit blijven
        # (wiki vertrouwt de index-status, geen live read_status-drop).
        hits = self.kb.recall_hits([0.9, 0.8, 0.7, 0.6], query_text="wiki",
                                   k=5, layers=("wiki",))
        self.assertTrue(any(h["layer"] == "wiki" for h in hits))

    def test_memory_hits_still_memory_only(self):
        hits = self.kb.memory_hits([0.1, 0.2, 0.3, 0.4], query_text="bug", k=5)
        self.assertTrue(all(Path(h["path"]).name == "m1.md" for h in hits))

    def test_has_fts_match_finds_keyword(self):
        # 'artikel' staat in de wiki-body -> FTS-match in de wiki-laag
        self.assertTrue(self.kb.has_fts_match("artikel", layer="wiki"))

    def test_has_fts_match_no_keyword(self):
        self.assertFalse(self.kb.has_fts_match("zwaluwparadox", layer="wiki"))

    def test_has_fts_match_failsoft_bad_query(self):
        # FTS5-syntax-tekens mogen niet crashen -> False
        self.assertFalse(self.kb.has_fts_match('"("', layer="wiki"))

    def test_wiki_hits_only_wiki(self):
        hits = self.kb.wiki_hits([0.9, 0.8, 0.7, 0.6], query_text="wiki", k=5)
        self.assertTrue(all(h["layer"] == "wiki" for h in hits))


if __name__ == "__main__":
    unittest.main()
