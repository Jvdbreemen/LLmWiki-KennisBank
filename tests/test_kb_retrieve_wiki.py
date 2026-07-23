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

    def test_prompt_embed_timeout_clamps_legacy_high_value(self):
        self.assertEqual(
            self.m._prompt_embed_timeout({"retrieve_timeout": 20.0}),
            2.0,
        )

    def test_prompt_embed_timeout_requires_explicit_ceiling_opt_in(self):
        with patch.dict(
            os.environ,
            {
                "KB_RETRIEVE_TIMEOUT": "4",
                "KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT": "4",
            },
        ):
            self.assertEqual(self.m._prompt_embed_timeout({}), 4.0)

    def test_main_bounds_single_embed_and_warms_on_miss(self):
        self.emb.embed = Mock(return_value=None)
        self.emb.warm_async = Mock()
        prompt = "een relevante vraag over het artikel"

        with patch.object(sys, "stdin", io.StringIO(json.dumps({"prompt": prompt}))):
            self.m.main()

        self.emb.embed.assert_called_once_with(prompt, timeout=2.0)
        self.emb.warm_async.assert_called_once_with()

    def test_cosine_relevant_injects_hybrid(self):
        self.emb.cosine = lambda a, b: 0.9  # boven drempel -> gate slaagt
        # Mock i.p.v. kale lambda: assert_called bewijst dat het hybride pad
        # DAADWERKELIJK is gelopen. Zonder die guard kan een signatuur-drift de
        # fail-soft except raken en stil naar de fallback vallen (false green).
        wiki_hits = Mock(side_effect=lambda qv, query_text="", k=3, expand=False: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "hybride treffer"}])
        self.m.kb_recall.wiki_hits = wiki_hits
        qvec = self.emb.embed("een relevante vraag over het artikel")
        text = self.m._wiki_block("een relevante vraag over het artikel",
                                  self.emb, self.vault_root, self._cfg(), qvec)
        self.assertIn("hybride treffer", text)
        self.assertIsNotNone(qvec)
        wiki_hits.assert_called()

    def test_fts_only_triggers_when_cosine_low(self):
        self.emb.cosine = lambda a, b: 0.1  # onder drempel -> alleen FTS kan triggeren
        has_fts = Mock(side_effect=lambda q, layer="wiki": True)
        wiki_hits = Mock(side_effect=lambda qv, query_text="", k=3, expand=False: [
            {"path": "/v/02-wiki/art.md", "layer": "wiki", "title": "Art",
             "created": "2026-06-01", "score": 0.5, "snippet": "exacte-term-treffer"}])
        self.m.kb_recall.has_fts_match = has_fts
        self.m.kb_recall.wiki_hits = wiki_hits
        qvec = self.emb.embed("FunctieNaamXYZ aanroep")
        text = self.m._wiki_block("FunctieNaamXYZ aanroep",
                                  self.emb, self.vault_root, self._cfg(), qvec)
        self.assertIn("exacte-term-treffer", text)
        has_fts.assert_called()   # FTS-gate is echt geraadpleegd
        wiki_hits.assert_called()  # en het hits-pad is echt gelopen

    def test_irrelevant_no_injection(self):
        self.emb.cosine = lambda a, b: 0.1
        has_fts = Mock(side_effect=lambda q, layer="wiki": False)
        self.m.kb_recall.has_fts_match = has_fts
        qvec = self.emb.embed("totaal iets anders zonder match")
        text = self.m._wiki_block("totaal iets anders zonder match",
                                  self.emb, self.vault_root, self._cfg(), qvec)
        self.assertEqual(text, "")
        has_fts.assert_called()  # de FTS-gate is echt geraadpleegd (geen stille skip)

    def test_fallback_to_cosine_when_hybrid_empty(self):
        self.emb.cosine = lambda a, b: 0.9  # gate slaagt
        wiki_hits = Mock(side_effect=lambda qv, query_text="", k=3, expand=False: [])  # index leeg
        self.m.kb_recall.wiki_hits = wiki_hits
        qvec = self.emb.embed("relevante vraag over het artikel")
        text = self.m._wiki_block("relevante vraag over het artikel",
                                  self.emb, self.vault_root, self._cfg(), qvec)
        # fallback naar cosine-cache-selectie: het wiki-artikel staat er
        self.assertIn("[[art]]", text)
        wiki_hits.assert_called()  # hybride is echt geprobeerd voordat de fallback liep


if __name__ == "__main__":
    unittest.main()
