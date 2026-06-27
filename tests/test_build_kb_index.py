"""Tests voor build-kb-index.py - de bouwer.

Monkeypatcht _embeddings zodat geen echt embedmodel nodig is: get_cached geeft
een deterministische fake-vector. Vault naar temp.
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DIM = 8


def _fake_vec(path, cache, recompute=True):
    # deterministisch op basis van de bestandsnaam
    h = sum(bytes(str(path), "utf-8")) % 97
    return [float((h + i) % 13) / 13.0 for i in range(DIM)]


class BuildKbIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-build-"))
        self.vault = self.tmp / "vault"
        (self.vault / ".claude" / "scripts").mkdir(parents=True)
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        # wiki-artikel
        (self.vault / "02-wiki" / "alpha.md").write_text(
            "---\ntitle: Alpha\nstatus: concept\n---\n\nAlpha body hook.", encoding="utf-8")
        # memory current + unverified
        (self.vault / "09-memory" / "m1.md").write_text(
            "---\ntitle: M1\ntype: memory\nstatus: current\ncreated: 2026-06-27\n---\n\nMemory een.",
            encoding="utf-8")
        (self.vault / "09-memory" / "m2.md").write_text(
            "---\ntitle: M2\ntype: memory\nstatus: unverified\ncreated: 2026-06-27\n---\n\nMemory twee.",
            encoding="utf-8")
        # importeer modules met de temp-vault actief
        for m in ("_vaultpath", "_embeddings", "_kbindex"):
            if m in sys.modules:
                importlib.reload(sys.modules[m])
        import _embeddings as emb
        self._orig_get_cached = emb.get_cached
        self._orig_embed_id = emb.embed_id
        self._orig_embed = emb.embed
        emb.get_cached = _fake_vec  # geen echt model
        emb.embed_id = lambda: "ollama:fake"
        # dim-probe zonder Ollama: builder roept emb.embed("dimensie-probe") aan
        emb.embed = lambda *a, **k: [0.1] * DIM
        self.emb = emb

    def tearDown(self):
        import shutil
        self.emb.get_cached = self._orig_get_cached
        self.emb.embed_id = self._orig_embed_id
        self.emb.embed = self._orig_embed
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, rebuild=False):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_kb_index", str(SCRIPTS_DIR / "build-kb-index.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main(rebuild=rebuild)
        return mod

    def test_build_indexes_wiki_and_current_memory_only(self):
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        paths = {r[0] for r in conn.execute("SELECT path FROM docs").fetchall()}
        conn.close()
        names = {Path(p).name for p in paths}
        self.assertIn("alpha.md", names)   # wiki
        self.assertIn("m1.md", names)      # memory current
        self.assertNotIn("m2.md", names)   # memory unverified -> niet geindexeerd

    def test_rebuild_is_idempotent(self):
        self._build(rebuild=True)
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        n = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        self.assertEqual(n, 2)  # alpha + m1, geen duplicaten

    def test_embed_index_false_excludes_wiki(self):
        """embed_index=false → wiki-docs worden niet geïndexeerd, memory wel."""
        settings_file = self.vault / "kennisbank-settings.json"
        import json
        settings_file.write_text(
            json.dumps({"embed_index": False, "memory_capture": True,
                        "auto_archive": False, "distill_notify": True,
                        "daily_graphify": False}),
            encoding="utf-8")
        import importlib, _settings
        importlib.reload(_settings)
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        names = {Path(p).name
                 for (p,) in conn.execute("SELECT path FROM docs").fetchall()}
        conn.close()
        self.assertNotIn("alpha.md", names, "wiki mag niet geïndexeerd zijn bij embed_index=false")
        self.assertIn("m1.md", names, "memory (current) moet geïndexeerd zijn ook bij embed_index=false")

    def test_memory_capture_false_excludes_memory(self):
        """memory_capture=false → memory-docs worden niet geïndexeerd, wiki wel."""
        settings_file = self.vault / "kennisbank-settings.json"
        import json
        settings_file.write_text(
            json.dumps({"embed_index": True, "memory_capture": False,
                        "auto_archive": False, "distill_notify": True,
                        "daily_graphify": False}),
            encoding="utf-8")
        import importlib, _settings
        importlib.reload(_settings)
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        names = {Path(p).name
                 for (p,) in conn.execute("SELECT path FROM docs").fetchall()}
        conn.close()
        self.assertNotIn("m1.md", names, "memory mag niet geïndexeerd zijn bij memory_capture=false")
        self.assertIn("alpha.md", names, "wiki moet geïndexeerd zijn ook bij memory_capture=false")

    def test_rebuild_with_model_down_leaves_index_intact(self):
        """--rebuild met embed=None (model onbereikbaar) mag bestaande index NIET wissen."""
        # Bouw eerst een geldige index op
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        n_before = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        self.assertGreater(n_before, 0, "precondition: index moet gevuld zijn")

        # Simuleer model-down: embed() → None
        self.emb.embed = lambda *a, **k: None
        self._build(rebuild=True)  # mag niet crashen
        self.emb.embed = lambda *a, **k: [0.1] * DIM  # herstel voor tearDown

        # Index-bestand moet nog bestaan en data intact zijn
        conn = _kbindex.connect()
        n_after = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        self.assertEqual(n_before, n_after,
                         "index mag niet gewist zijn als het embedmodel onbereikbaar is")

    def test_incremental_skip_does_not_reindex_unchanged_files(self):
        """Tweede build (rebuild=False) slaat ongewijzigde files over: doc-count stabiel."""
        self._build(rebuild=True)
        import _kbindex
        conn = _kbindex.connect()
        n_first = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        # Tweede build zonder wijzigingen: niets mag worden verwijderd of toegevoegd
        self._build(rebuild=False)
        conn = _kbindex.connect()
        n_second = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
        conn.close()
        self.assertEqual(n_first, n_second,
                         "incremental build mag het doc-aantal niet wijzigen als files ongewijzigd zijn")


if __name__ == "__main__":
    unittest.main()
