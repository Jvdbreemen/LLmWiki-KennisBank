"""Instruction prefixes on the query and document side of the embed backend.

Why this is tested: e5-instruct is trained with "Instruct: ...\\nQuery: " in
front of the question; embed without it and you measure and use a different
model than you think. At the same time the prefix must never switch on
silently -- that would invalidate every vector already in the cache without
anyone noticing. The two requirements together: off by default, and the moment
it is on, embed_id() moves with it.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _embeddings as emb  # noqa: E402


class TestEmbedPrefix(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in
                      ("KB_EMBED_QUERY_PREFIX", "KB_EMBED_DOC_PREFIX",
                       "KB_EMBED_MODEL", "KB_EMBED_PROVIDER", "KENNISBANK_VAULT")}
        for k in self.saved:
            os.environ.pop(k, None)
        # An empty vault, so "the default" means the code's default and not
        # "whatever this machine happens to have configured". Without this the
        # suite passes or fails on the contents of kennisbank-embed.json: adding
        # a query_prefix there broke these two tests while the code was correct.
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["KENNISBANK_VAULT"] = self._tmp.name
        os.environ["KB_EMBED_PROVIDER"] = "ollama"
        os.environ["KB_EMBED_MODEL"] = "testmodel"
        self.sent = []
        self._orig = emb._http_json
        emb._http_json = lambda url, payload, headers, timeout: (
            self.sent.append(payload) or {"embedding": [0.1, 0.2]})

    def tearDown(self):
        emb._http_json = self._orig
        self._tmp.cleanup()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_is_no_prefix(self):
        """Without config the text reaches the backend unchanged."""
        emb.embed("a question", kind="query")
        self.assertEqual(self.sent[0]["prompt"], "a question")

    def test_query_prefix_applies_only_to_queries(self):
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        emb.embed("a question", kind="query")
        emb.embed("a document", kind="doc")
        emb.embed("bare", kind="")
        self.assertEqual(self.sent[0]["prompt"], "Query: a question")
        self.assertEqual(self.sent[1]["prompt"], "a document")
        self.assertEqual(self.sent[2]["prompt"], "bare")

    def test_doc_prefix_applies_only_to_docs(self):
        os.environ["KB_EMBED_DOC_PREFIX"] = "passage: "
        emb.embed("a question", kind="query")
        emb.embed("a document", kind="doc")
        self.assertEqual(self.sent[0]["prompt"], "a question")
        self.assertEqual(self.sent[1]["prompt"], "passage: a document")

    def test_empty_env_var_disables_a_configured_prefix(self):
        """An explicitly empty value means "no prefix", not "unset".

        Treating "" as unset would make KB_EMBED_QUERY_PREFIX= fall through to
        the configured value, so a prefix could not be switched off for a single
        run -- and embed_id() would keep tracking the config behind your back.
        """
        os.environ["KB_EMBED_QUERY_PREFIX"] = ""
        emb.embed("a question", kind="query")
        self.assertEqual(self.sent[0]["prompt"], "a question")

    def test_escaped_newline_in_prefix_becomes_a_real_newline(self):
        """e5 wants a real line break between instruction and question, but an
        env var cannot hold one, so \\n in the config has to be translated."""
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Instruct: search\\nQuery: "
        emb.embed("a question", kind="query")
        self.assertEqual(self.sent[0]["prompt"], "Instruct: search\nQuery: a question")

    def test_doc_prefix_changes_embed_id_so_the_cache_invalidates(self):
        """The same text under a different document prefix yields a different
        vector. Reusing across that is exactly as wrong as reusing across a
        model change, so embed_id() has to move with it."""
        plain = emb.embed_id()
        os.environ["KB_EMBED_DOC_PREFIX"] = "passage: "
        self.assertNotEqual(plain, emb.embed_id())

    def test_query_prefix_does_not_change_embed_id(self):
        """The cache holds document vectors only; the query prefix does not
        touch them, and folding it in would force a full re-embed of the vault
        on every A/B run."""
        plain = emb.embed_id()
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        self.assertEqual(plain, emb.embed_id())

    def test_embed_query_seam_applies_the_configured_prefix(self):
        """TASK-184: the one query-side entry point carries the kind, so a
        call site cannot forget it."""
        emb.embed_query("a question")
        self.assertEqual(self.sent[0]["prompt"], "a question")
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        emb.embed_query("a question")
        self.assertEqual(self.sent[1]["prompt"], "Query: a question")

    def test_query_embed_id_moves_with_the_query_prefix(self):
        """Query-vector caches key on query_embed_id(): the same question
        under a different query prefix is a different vector. embed_id()
        (the document cache) must NOT move — pinned above."""
        plain = emb.query_embed_id()
        doc_id = emb.embed_id()
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        self.assertNotEqual(plain, emb.query_embed_id())
        self.assertEqual(doc_id, emb.embed_id())


if __name__ == "__main__":
    unittest.main()
