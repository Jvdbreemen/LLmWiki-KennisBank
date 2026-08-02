"""Instructieprefixen aan de query- en documentzijde van de embed-backend.

Waarom dit getest wordt: e5-instruct is getraind met "Instruct: ...\\nQuery: "
voor de vraag; embed je zonder, dan meet en gebruik je een ander model dan je
denkt. Tegelijk mag de prefix nooit stilzwijgend aanstaan -- dat zou elke
bestaande vector in de cache ongeldig maken zonder dat iemand het merkt. De
twee eisen samen: default uit, en zodra hij aanstaat verandert embed_id() mee.
"""
import os
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _embeddings as emb  # noqa: E402


class TestEmbedPrefix(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in
                      ("KB_EMBED_QUERY_PREFIX", "KB_EMBED_DOC_PREFIX",
                       "KB_EMBED_MODEL", "KB_EMBED_PROVIDER")}
        for k in self.saved:
            os.environ.pop(k, None)
        os.environ["KB_EMBED_PROVIDER"] = "ollama"
        os.environ["KB_EMBED_MODEL"] = "testmodel"
        self.sent = []
        self._orig = emb._http_json
        emb._http_json = lambda url, payload, headers, timeout: (
            self.sent.append(payload) or {"embedding": [0.1, 0.2]})

    def tearDown(self):
        emb._http_json = self._orig
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_is_no_prefix(self):
        """Zonder config gaat de tekst ongewijzigd de backend in."""
        emb.embed("een vraag", kind="query")
        self.assertEqual(self.sent[0]["prompt"], "een vraag")

    def test_query_prefix_applies_only_to_queries(self):
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        emb.embed("een vraag", kind="query")
        emb.embed("een document", kind="doc")
        emb.embed("kaal", kind="")
        self.assertEqual(self.sent[0]["prompt"], "Query: een vraag")
        self.assertEqual(self.sent[1]["prompt"], "een document")
        self.assertEqual(self.sent[2]["prompt"], "kaal")

    def test_doc_prefix_applies_only_to_docs(self):
        os.environ["KB_EMBED_DOC_PREFIX"] = "passage: "
        emb.embed("een vraag", kind="query")
        emb.embed("een document", kind="doc")
        self.assertEqual(self.sent[0]["prompt"], "een vraag")
        self.assertEqual(self.sent[1]["prompt"], "passage: een document")

    def test_escaped_newline_in_prefix_becomes_a_real_newline(self):
        """e5 wil een echte regelovergang tussen instructie en vraag, maar een
        env-var kan er geen bevatten; \\n in de config moet dus vertaald worden."""
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Instruct: zoek\\nQuery: "
        emb.embed("een vraag", kind="query")
        self.assertEqual(self.sent[0]["prompt"], "Instruct: zoek\nQuery: een vraag")

    def test_doc_prefix_changes_embed_id_so_the_cache_invalidates(self):
        """Dezelfde tekst met een andere documentprefix levert een andere vector.
        Hergebruik daaroverheen is net zo fout als hergebruik over een
        modelwissel heen, dus embed_id() moet meebewegen."""
        plain = emb.embed_id()
        os.environ["KB_EMBED_DOC_PREFIX"] = "passage: "
        self.assertNotEqual(plain, emb.embed_id())

    def test_query_prefix_does_not_change_embed_id(self):
        """De cache bevat alleen documentvectoren; de queryprefix raakt die
        niet, en zou anders bij elke A/B-run een volledige herberekening van
        de hele vault forceren."""
        plain = emb.embed_id()
        os.environ["KB_EMBED_QUERY_PREFIX"] = "Query: "
        self.assertEqual(plain, emb.embed_id())


if __name__ == "__main__":
    unittest.main()
