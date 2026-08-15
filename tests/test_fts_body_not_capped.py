"""The lexical arm was paying the embedding model's context limit.

`doc_text` caps a document at 4000 characters because the embedding model runs
at `num_ctx=2048` — a setting chosen to free 2.18 GB of VRAM, and above which
the embed call does not truncate but fails outright. That constraint belongs to
the vector arm. FTS5 has no context window, and `build-kb-index` was handing it
the same truncated string, so 16.6% of the wiki was unreachable by EITHER arm of
a hybrid search (TASK-164).

Measured on the live vault: recall@5 on questions about content past the cap
went 0.450 → 0.725 when FTS got the whole body, with the 329-question set
unchanged at 1.000.

These tests drive the real builder and then ask the real search, because the
claim is about what can be FOUND, not about what a constant is set to.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DIM = 8
#: Far enough past the 4000-character embedding cap that no rounding hides it.
#: One token, no hyphen: FTS5 reads `-` as an operator, so a hyphenated marker
#: would fail on query syntax rather than on what this test is about.
TAIL_MARKER = "zeldzaamwoordkanariemarkering"


def _fake_vec(path, cache, recompute=True):
    h = sum(bytes(str(path), "utf-8")) % 97
    return [float((h + i) % 13) / 13.0 for i in range(DIM)]


class FtsBodyNotCappedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-fts-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

        # One long article whose only distinctive term sits well past the cap.
        filler = "gewone vultekst over een alledaags onderwerp. " * 200  # ~9200
        (self.vault / "02-wiki" / "lang.md").write_text(
            "---\ntitle: Lang\nstatus: concept\n---\n\n"
            f"{filler}\n\n## {TAIL_MARKER}\n\nHier staat de uitleg.\n",
            encoding="utf-8")
        # A short article, so the corpus is not a single document.
        (self.vault / "02-wiki" / "kort.md").write_text(
            "---\ntitle: Kort\nstatus: concept\n---\n\nKorte inhoud.\n",
            encoding="utf-8")

        for m in ("_vaultpath", "_embeddings", "_kbindex"):
            if m in sys.modules:
                importlib.reload(sys.modules[m])
        import _embeddings as emb
        self._orig = (emb.get_cached, emb.embed_id, emb.embed)
        emb.get_cached = _fake_vec
        emb.embed_id = lambda: "ollama:fake"
        emb.embed = lambda *a, **k: [0.1] * DIM
        self.emb = emb

    def tearDown(self):
        (self.emb.get_cached, self.emb.embed_id, self.emb.embed) = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self):
        spec = importlib.util.spec_from_file_location(
            "build_kb_index_fts", str(SCRIPTS_DIR / "build-kb-index.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main(rebuild=True)
        return mod

    def test_the_marker_past_the_cap_is_findable(self):
        """The whole point: a term beyond 4000 characters must be searchable."""
        self._build()
        import _kbindex
        conn = _kbindex.connect()
        try:
            hit = conn.execute(
                "SELECT docs.path FROM fts_docs JOIN docs ON docs.doc_id = fts_docs.rowid "
                "WHERE fts_docs MATCH ?", (TAIL_MARKER,)).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(hit), 1, "the tail marker is not in the FTS index")
        self.assertEqual(Path(hit[0][0]).name, "lang.md")

    def test_the_stored_body_runs_past_the_embedding_cap(self):
        self._build()
        import _embeddings as emb
        import _kbindex
        conn = _kbindex.connect()
        try:
            longest = conn.execute("SELECT max(length(body)) FROM fts_docs").fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(longest, 4000)
        # And the embedding path keeps its own, smaller cap: raising THAT would
        # not truncate those documents, it would drop them out of the index,
        # because the backend fails rather than truncating above num_ctx.
        self.assertEqual(
            len(emb.doc_text(self.vault / "02-wiki" / "lang.md")), 4000)

    def test_a_short_article_is_unaffected(self):
        """The change may not alter what already worked."""
        self._build()
        import _kbindex
        conn = _kbindex.connect()
        try:
            row = conn.execute(
                "SELECT body FROM fts_docs JOIN docs ON docs.doc_id = fts_docs.rowid "
                "WHERE docs.path LIKE '%kort.md'").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertIn("Korte inhoud", row[0])


if __name__ == "__main__":
    unittest.main()
