"""Een koud embedding-model moet gemeld worden, niet stil weggeslikt.

De hook faalt bewust open: geen model = geen injectie. Maar zwijgen bij een
misser is erger dan geen kennisbank, want de gebruiker gaat er dan van uit dat
de vault meekeek. Deze tests leggen vast dat een misser zichtbaar wordt, dat de
opwarm-actie alsnog start, en dat de melding nooit de prompt kan breken.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


class ColdNoticeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cold-"))
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mod = load_script("kb-retrieve.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_melding_is_zichtbaar(self):
        """suppressOutput=False, anders leest alleen het model de melding."""
        import io
        buf, saved = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            self.mod._emit_notice("test-melding")
        finally:
            sys.stdout = saved
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["suppressOutput"])
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("test-melding", payload["hookSpecificOutput"]["additionalContext"])

    def test_geslaagde_injectie_blijft_onzichtbaar(self):
        """Een treffer hoort de gebruiker NIET te storen; alleen de misser wel."""
        import io
        buf, saved = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            self.mod._emit("gewone context")
        finally:
            sys.stdout = saved
        self.assertTrue(json.loads(buf.getvalue())["suppressOutput"])

    def test_lege_melding_schrijft_niets(self):
        import io
        buf, saved = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            self.mod._emit_notice("")
        finally:
            sys.stdout = saved
        self.assertEqual(buf.getvalue(), "")

    def test_tekst_noemt_de_timeout_en_de_vervolgstap(self):
        txt = self.mod._cold_notice(already_warming=False, timeout=2.0)
        self.assertIn("2s", txt)
        self.assertIn("30 seconden", txt)
        # Geen valse belofte van een automatische retry.
        self.assertIn("niet zelf opnieuw proberen", txt)

    def test_tekst_verschilt_als_er_al_een_warmup_loopt(self):
        """Anders zou de hook 'wordt nu geladen' beweren terwijl het sentinel-
        venster van warm_async een tweede start juist onderdrukt."""
        lopend = self.mod._cold_notice(already_warming=True, timeout=2.0)
        nieuw = self.mod._cold_notice(already_warming=False, timeout=2.0)
        self.assertNotEqual(lopend, nieuw)
        self.assertIn("loopt al", lopend)

    def test_warm_detectie_faalt_open(self):
        """Een kapotte emb-module mag geen exception naar de hot path lekken."""
        class Kapot:
            def _warm_marker(self):
                raise RuntimeError("stuk")
        self.assertFalse(self.mod._warm_already_running(Kapot()))

    def test_warm_detectie_leest_de_marker(self):
        marker = self.tmp / "marker"
        marker.write_text("", encoding="utf-8")

        class Emb:
            def _warm_marker(_self):
                return marker
        self.assertTrue(self.mod._warm_already_running(Emb()))
        os.utime(marker, (0, 0))  # ver in het verleden -> buiten het venster
        self.assertFalse(self.mod._warm_already_running(Emb()))


if __name__ == "__main__":
    unittest.main()
