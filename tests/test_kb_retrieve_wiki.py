"""Tests voor de hybride wiki-injectie in kb-retrieve._wiki_block. Geen model:
we injecteren qvec/cosine/hits via monkeypatch op de helpers."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_hook():
    spec = importlib.util.spec_from_file_location("kb_retrieve", str(SCRIPTS_DIR / "kb-retrieve.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class WikiBlockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-wiki-"))
        self.vault = self.tmp / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.m = _load_hook()
        import _embeddings as emb
        from _vaultpath import vault_root
        self.emb, self.vault_root = emb, vault_root
        # fake emb: één wiki-kandidaat in de cache, embed geeft qvec
        self._orig = (
            emb.load_cache,
            emb.embed,
            emb.cosine,
            emb.doc_text,
            emb.embed_id,
            emb.warm_async,
        )
        wpath = str(self.vault / "02-wiki" / "art.md")
        emb.embed_id = lambda: "ollama:test"
        emb.load_cache = lambda: {wpath: {"id": "ollama:test", "embedding": [0.1, 0.2], "dim": 2}}
        emb.embed = lambda text, timeout=20.0: [0.1, 0.2]
        emb.doc_text = lambda p, cap=280: "wiki body"

    def tearDown(self):
        import shutil
        (
            self.emb.load_cache,
            self.emb.embed,
            self.emb.cosine,
            self.emb.doc_text,
            self.emb.embed_id,
            self.emb.warm_async,
        ) = self._orig
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cfg(self):
        return {}

    def _prompt_env(self, **overrides):
        env = {"KENNISBANK_VAULT": str(self.vault)}
        env.update(overrides)
        return patch.dict(os.environ, env, clear=True)

    def test_prompt_embed_timeout_clamps_legacy_high_value(self):
        with self._prompt_env():
            self.assertEqual(
                self.m._prompt_embed_timeout({"retrieve_timeout": 20.0}),
                2.0,
            )

    def test_prompt_embed_timeout_requires_explicit_ceiling_opt_in(self):
        with self._prompt_env(
            KB_RETRIEVE_TIMEOUT="4",
            KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT="4",
        ):
            self.assertEqual(self.m._prompt_embed_timeout({}), 4.0)

    def test_main_bounds_single_embed_and_warms_on_miss(self):
        self.emb.embed = Mock(return_value=None)
        self.emb.warm_async = Mock()
        prompt = "een relevante vraag over het artikel"

        with self._prompt_env():
            with patch.object(
                sys,
                "stdin",
                io.StringIO(json.dumps({"prompt": prompt})),
            ):
                self.m.main()

        self.emb.embed.assert_called_once_with(prompt, timeout=2.0)
        self.emb.warm_async.assert_called_once_with()

    def test_cosine_relevant_injects_hybrid(self):
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        self.emb.cosine = lambda a, b: 0.9  # boven drempel -> gate slaagt
        # Mock i.p.v. kale lambda: assert_called bewijst dat het hybride pad
        # DAADWERKELIJK is gelopen. Zonder die guard kan een signatuur-drift de
        # fail-soft except raken en stil naar de fallback vallen (false green).
        wiki_hits = Mock(side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "hybride treffer"}])
        self.m.kb_recall.wiki_hits = wiki_hits
        qvec = self.emb.embed("een relevante vraag over het artikel")
        text = self.m._wiki_block("een relevante vraag over het artikel",
                                  self.emb, self.vault_root, self._cfg(), qvec)
        self.assertIn("hybride treffer", text)
        self.assertIsNotNone(qvec)
        wiki_hits.assert_called()

    def test_fts_gate_is_the_indexs_job_not_the_blocks(self):
        """De FTS-poort zat in het cache-pad; de index doet die nu zelf.

        Vroeger raadpleegde dit blok has_fts_match om te beslissen of een lage
        cosine alsnog mocht injecteren. Dat hoorde bij de terugvalweg. Op de
        gated weg past search() de drempel EN de FTS-fusie zelf toe, dus het
        blok hoort die vraag niet nog eens te stellen."""
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        has_fts = Mock(return_value=True)
        self.m.kb_recall.has_fts_match = has_fts
        wiki_hits = Mock(side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "exacte-term-treffer"}])
        self.m.kb_recall.wiki_hits = wiki_hits
        text = self.m._wiki_block("FunctieNaamXYZ aanroep", self.emb,
                                  self.vault_root, self._cfg(), [0.1, 0.2])
        self.assertIn("exacte-term-treffer", text)
        wiki_hits.assert_called()
        has_fts.assert_not_called()

    def test_missing_index_returns_the_sentinel_not_an_empty_block(self):
        """Zonder bruikbare index is "niets gevonden" een LEUGEN.

        Hier stond een terugvalweg die de volledige embedding-cache parseerde:
        gemeten 6766 ms en 186 MB op een pad met een budget van 2,0 s, en hij
        vuurde juist tijdens een index-herbouw. Het blok geeft nu een sentinel
        terug zodat main() het verschil kan maken tussen "de index leverde
        niets" en "er was geen index"."""
        self.m.kb_recall.index_is_gated = Mock(return_value=False)
        out = self.m._wiki_block("een vraag", self.emb, self.vault_root,
                                 self._cfg(), [0.1, 0.2])
        self.assertIs(out, self.m._NO_INDEX)

    def test_a_broken_index_also_returns_the_sentinel(self):
        """Een exception op de gated weg mag niet stil als 'geen treffers' lezen."""
        self.m.kb_recall.index_is_gated = Mock(side_effect=RuntimeError("db stuk"))
        out = self.m._wiki_block("een vraag", self.emb, self.vault_root,
                                 self._cfg(), [0.1, 0.2])
        self.assertIs(out, self.m._NO_INDEX)

    def test_the_json_cache_is_never_read_even_without_an_index(self):
        """De 170 MB cache mag nergens meer op de hot path staan."""
        self.m.kb_recall.index_is_gated = Mock(return_value=False)
        load_cache = Mock(side_effect=AssertionError("load_cache op de hot path"))
        self.emb.load_cache = load_cache
        self.m._wiki_block("een vraag", self.emb, self.vault_root,
                           self._cfg(), [0.1, 0.2])
        load_cache.assert_not_called()

    # --- JSON-cache van de hot path (TASK-62) ---

    def test_wiki_block_never_touches_json_cache_when_index_is_gated(self):
        """De cache van tientallen MB hoort niet op de hot path te staan.

        Zodra de index zelf kan drempelen levert hij poort én selectie; de
        JSON-cache is dan overbodig werk.
        """
        boom = Mock(side_effect=AssertionError("load_cache op de hot path aangeroepen"))
        self.emb.load_cache = boom
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        self.m.kb_recall.wiki_hits = Mock(
            side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [
                {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
                 "created": "2026-06-01", "score": 0.5, "snippet": "index-treffer"}])
        qvec = [0.1, 0.2]
        text = self.m._wiki_block("een vraag", self.emb, self.vault_root, self._cfg(), qvec)
        self.assertIn("index-treffer", text)
        boom.assert_not_called()

    def test_wiki_block_works_without_a_json_cache_at_all(self):
        """Een vault met werkende index maar zonder JSON-cache gaf een leeg blok."""
        self.emb.load_cache = lambda: {}
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        self.m.kb_recall.wiki_hits = Mock(
            side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [
                {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
                 "created": "2026-06-01", "score": 0.5, "snippet": "nog steeds gevonden"}])
        text = self.m._wiki_block("een vraag", self.emb, self.vault_root, self._cfg(), [0.1, 0.2])
        self.assertIn("nog steeds gevonden", text)

    def test_ungated_index_never_injects_unfiltered(self):
        """Index van vóór de normalisatie mag nooit onvoorwaardelijk injecteren.

        Dat was de reden dat de terugvalweg bestond. Die weg is weg, maar de
        eis blijft: een ongated index levert geen tekst, hij levert de sentinel
        waarop main() een zichtbare melding doet.
        """
        self.m.kb_recall.index_is_gated = Mock(return_value=False)
        wiki_hits = Mock(return_value=[{"path": "/v/02-wiki/art.md", "layer": "wiki",
                                        "title": "Art", "created": "2026-06-01",
                                        "score": 0.5, "snippet": "ongefilterd"}])
        self.m.kb_recall.wiki_hits = wiki_hits
        out = self.m._wiki_block("totaal iets anders", self.emb, self.vault_root,
                                 self._cfg(), [0.1, 0.2])
        self.assertIs(out, self.m._NO_INDEX)
        wiki_hits.assert_not_called()

    def test_gated_index_without_hits_injects_nothing(self):
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        self.m.kb_recall.wiki_hits = Mock(
            side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [])
        text = self.m._wiki_block("iets irrelevants", self.emb, self.vault_root,
                                  self._cfg(), [0.1, 0.2])
        self.assertEqual(text, "")

    # --- Injectiepad end-to-end (TASK-86, claude-mem-les) ---

    def test_main_injects_ranked_stems_into_hook_output(self):
        """Wat de ranking teruggeeft moet ook echt in de hook-OUTPUT belanden.

        Bij claude-mem viel een hele geheugencategorie maandenlang stil buiten
        de contextinjectie zonder dat iemand het merkte (fix pas in v13.12.4):
        de ranking was goed, de injectie niet, en niets mat het verschil. Deze
        test parseert daarom de volledige stdout van main() en asserteert dat
        de verwachte stem als [[wikilink]] in additionalContext staat — niet
        alleen dat wiki_hits hem teruggaf.
        """
        self.emb.cosine = lambda a, b: 0.9
        self.m.kb_recall.index_is_gated = Mock(return_value=True)
        self.m.kb_recall.wiki_hits = Mock(
            side_effect=lambda qv, query_text="", k=3, expand=False, min_cos=0.0: [
                {"path": str(self.vault / "02-wiki" / "art.md"), "layer": "wiki",
                 "title": "Art", "created": "2026-06-01", "score": 0.83,
                 "snippet": "e2e-injectie-snippet"}])
        prompt = "een relevante vraag over het artikel"
        buf = io.StringIO()
        with self._prompt_env():
            with patch.object(sys, "stdin", io.StringIO(json.dumps({"prompt": prompt}))):
                with patch.object(sys, "stdout", buf):
                    self.m.main()
        raw = buf.getvalue()
        self.assertTrue(raw.strip(), "hook emitteerde niets terwijl er een hit was")
        out = json.loads(raw)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("[[art]]", ctx)
        self.assertIn("e2e-injectie-snippet", ctx)


if __name__ == "__main__":
    unittest.main()
