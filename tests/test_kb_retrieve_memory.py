"""Tests voor de additieve memory-injectie in kb-retrieve.py.

Twee testklassen:

1. KbRetrieveMemoryTest — subprocess-guard tests (geen Ollama nodig).
   Draait de hook als subprocess met stdin-JSON (echt hook-contract). Toetst
   de twee invarianten zonder embedmodel:
     a. memory_recall=false -> output bevat NOOIT een memory-blok (byte-identiteit
        met wiki-only: geen 'KennisBank-geheugen'-regel).
     b. Een triviale/korte prompt -> geen output (bestaand gedrag, ongewijzigd).

2. KbRetrieveMemoryBlockTest — unit tests voor _memory_block (MINOR 2).
   Laadt kb-retrieve.py via importlib en injecteert een stub hits_fn zodat de
   gehele formatting- en hits-flow toetsbaar is zonder Ollama of kb-index.
"""
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK = SCRIPTS_DIR / "kb-retrieve.py"


def _load_kb_retrieve():
    spec = importlib.util.spec_from_file_location("kb_retrieve", str(HOOK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retrieve_context_requests_raw_output_suppression():
    mod = _load_kb_retrieve()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        mod._emit("relevant local context")
    payload = json.loads(output.getvalue())
    assert payload["suppressOutput"] is True
    assert (
        payload["hookSpecificOutput"]["additionalContext"]
        == "relevant local context"
    )


class KbRetrieveMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ret-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, prompt: str, settings: dict | None = None) -> str:
        if settings is not None:
            (self.vault / "kennisbank-settings.json").write_text(
                json.dumps(settings), encoding="utf-8")
        p = subprocess.run([sys.executable, str(HOOK)],
                           input=json.dumps({"prompt": prompt}),
                           capture_output=True, text=True, env=self.env, timeout=60)
        return p.stdout

    def test_trivial_prompt_no_output(self):
        self.assertEqual(self._run("ok").strip(), "")

    def test_memory_recall_off_no_memory_block(self):
        # geen index, geen cache -> hoogstens niets; cruciaal: nooit een memory-blok
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": False})
        self.assertNotIn("KennisBank-geheugen", out)

    def test_memory_recall_on_without_index_still_no_crash(self):
        # memory aan maar geen kb-index.db -> fail-soft, geen memory-blok, geen crash
        out = self._run("Een wat langere vraag over hooks en retrieval in dit project",
                        settings={"memory_recall": True})
        self.assertNotIn("KennisBank-geheugen", out)  # index ontbreekt -> geen hits


class KbRetrieveMemoryBlockTest(unittest.TestCase):
    """Unit tests voor _memory_block met injectable hits_fn (geen Ollama nodig).

    Bewijst dat de formatting-logica en de hits-flow correct zijn zonder een
    echt embedmodel of kb-index.db te gebruiken (MINOR 2).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ret-blk-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = _load_kb_retrieve()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_memory_block_with_hits_returns_formatted_block(self):
        """Stub-hits resulteren in een blok met KennisBank-geheugen en [[stem]]."""
        fake_hits = [{"path": "/x/foo.md", "title": "Foo", "created": "2026-06-01",
                      "score": 0.9, "snippet": "iets"}]
        # Mock i.p.v. kale lambda: assert_called bewijst dat _memory_block de
        # hits_fn echt aanroept i.p.v. stil een leeg blok te produceren.
        hits_fn = Mock(side_effect=lambda *a, **k: fake_hits)
        result = self.mod._memory_block(
            [0.1, 0.2], "test prompt", {}, hits_fn=hits_fn)
        self.assertIn("KennisBank-geheugen", result)
        self.assertIn("[[foo]]", result)
        hits_fn.assert_called()

    def test_memory_block_with_no_hits_returns_empty_string(self):
        """Lege hits_fn -> leeg resultaat (geen kopregels, geen ruis)."""
        hits_fn = Mock(side_effect=lambda *a, **k: [])
        result = self.mod._memory_block(
            [0.1, 0.2], "test prompt", {}, hits_fn=hits_fn)
        self.assertEqual(result, "")
        hits_fn.assert_called()


@unittest.skipUnless(
    os.environ.get("KB_INTEGRATION") == "1",
    "integratie-tier: zet KB_INTEGRATION=1 (vereist een draaiende Ollama met het "
    "embedmodel). Default geskipt zodat de unit-CI hermetisch en snel blijft.")
class KbRetrieveIntegrationTest(unittest.TestCase):
    """Opt-in end-to-end: de ECHTE embed->cache(index)->retrieval-pijplijn.

    Dit is precies het pad dat de unit-suite bewust DOOD pint (tests/__init__.py):
    hier draaien we het één keer echt, tegen een mini-fixture, zodat het volledige
    pad ook daadwerkelijk gedekt is (nu alleen /kb-eval het handmatig raakt).

    Gated op KB_INTEGRATION=1: de suite-hermeticiteit (dead endpoint) wordt in
    tests/__init__.py overgeslagen wanneer die vlag staat, zodat emb.embed de
    echte Ollama bereikt. Op CI (geen Ollama, vlag niet gezet) blijft dit geskipt.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-int-"))
        self.vault = self.tmp / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # lage drempel: we toetsen de PLUMBING (embed->cache->select), niet de
        # exacte similarity-waarde van dit modelpaar.
        self._saved_thr = os.environ.get("KB_RETRIEVE_THRESHOLD")
        os.environ["KB_RETRIEVE_THRESHOLD"] = "0.1"
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.mod = _load_kb_retrieve()
        import _embeddings as emb
        from _vaultpath import vault_root
        self.emb, self.vault_root = emb, vault_root

    def tearDown(self):
        for key, saved in (("KENNISBANK_VAULT", self._saved),
                           ("KB_RETRIEVE_THRESHOLD", self._saved_thr)):
            if saved is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_real_embed_index_retrieval_roundtrip(self):
        note = self.vault / "02-wiki" / "art.md"
        note.write_text(
            "---\ntitle: OpenTherm MQTT configuratie\n---\n"
            "Zo configureer je de MQTT-broker voor de OpenTherm-gateway: "
            "vul broker-host, poort en credentials in bij de instellingen.\n",
            encoding="utf-8")

        # ECHTE embed van de note (raakt Ollama) -> in-memory cache (de 'index').
        body = self.emb.doc_text(note)
        vec = self.emb.embed(body)
        self.assertTrue(vec, "integratie vereist een bereikbaar embedmodel; kreeg geen vector")
        cache = {str(note): {"hash": self.emb.file_hash(note), "id": self.emb.embed_id(),
                             "dim": len(vec), "embedding": vec}}
        orig_load = self.emb.load_cache
        self.emb.load_cache = lambda: cache
        try:
            # ECHTE query-embed + cosine-selectie tegen de cache -> retrieval.
            # qvec wordt nu eenmalig door de caller berekend en doorgegeven.
            query = "Hoe stel ik de MQTT-broker in voor de OpenTherm gateway?"
            qvec = self.emb.embed(query)
            self.assertIsNotNone(qvec)
            text = self.mod._wiki_block(query, self.emb, self.vault_root, {}, qvec)
        finally:
            self.emb.load_cache = orig_load
        self.assertIn("[[art]]", text)


if __name__ == "__main__":
    unittest.main()
