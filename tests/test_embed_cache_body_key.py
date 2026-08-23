"""De embedding-cache sleutelt op de body, niet op de bytes van het bestand.

doc_text() strips de frontmatter, dus alleen de body wordt ooit geembed. Toch
invalideerde de cache op file_hash(). Een statuswissel `unverified` -> `current`
herschreef de frontmatter, veranderde de file-hash en dwong een herberekening af
die een bit-identieke vector opleverde. Gemeten op een echte vault: 578
promoties over twee dagen, dus 578 overbodige embeddings, elk bovendien goed
voor een volledige herschrijving van een cachebestand van 300 MB.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _embeddings as emb  # noqa: E402

BODY = "De router draait RouterOS 7.24 en de bootloader is bijgewerkt."


class EmbedCacheBodyKeyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-embcache-"))
        self.f = self.tmp / "m.md"
        self._write("unverified")
        self.calls = 0
        self._echt_embed = emb.embed
        self._echt_id = emb.embed_id
        emb.embed = self._nep_embed
        emb.embed_id = lambda: "testmodel:1"

    def tearDown(self):
        import shutil
        emb.embed = self._echt_embed
        emb.embed_id = self._echt_id
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _nep_embed(self, *a, **k):
        self.calls += 1
        return [0.1, 0.2, 0.3]

    def _write(self, status: str, body: str = BODY):
        self.f.write_text(
            f"---\ntype: memory\nstatus: {status}\ncreated: 2026-08-23\n---\n\n{body}\n",
            encoding="utf-8")

    def test_statuswissel_is_een_cache_hit(self):
        """De regressie: alleen de frontmatter wijzigt, de vector kan niet bewegen."""
        cache: dict = {}
        self.assertIsNotNone(emb.get_cached(self.f, cache))
        self.assertEqual(self.calls, 1, "eerste keer embedt hij")

        voor = emb.file_hash(self.f)
        self._write("current")
        self.assertNotEqual(emb.file_hash(self.f), voor,
                            "opzet: de file-hash verandert wel degelijk")

        self.assertIsNotNone(emb.get_cached(self.f, cache))
        self.assertEqual(self.calls, 1,
                         "een statuswissel mag geen herberekening kosten")

    def test_body_wijziging_is_een_cache_miss(self):
        cache: dict = {}
        emb.get_cached(self.f, cache)
        self.assertEqual(self.calls, 1)
        self._write("unverified", body="Een heel andere bewering.")
        emb.get_cached(self.f, cache)
        self.assertEqual(self.calls, 2, "een andere body moet wel opnieuw")

    def test_oude_cache_zonder_text_hash_migreert_zonder_herberekening(self):
        """Een bestaande cache mag geen volledige her-embedding afdwingen."""
        cache = {str(self.f): {"hash": emb.file_hash(self.f), "id": "testmodel:1",
                               "dim": 3, "embedding": [0.1, 0.2, 0.3]}}
        self.assertIsNotNone(emb.get_cached(self.f, cache))
        self.assertEqual(self.calls, 0, "oude entry blijft geldig")
        self.assertIn("text_hash", cache[str(self.f)],
                      "en wordt ter plekke bijgewerkt")

    def test_ander_model_blijft_altijd_een_miss(self):
        cache: dict = {}
        emb.get_cached(self.f, cache)
        self.assertEqual(self.calls, 1)
        emb.embed_id = lambda: "anandermodel:1"
        emb.get_cached(self.f, cache)
        self.assertEqual(self.calls, 2,
                         "vectoren van twee modellen worden nooit gemengd")


if __name__ == "__main__":
    unittest.main()
