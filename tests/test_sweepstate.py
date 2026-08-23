"""Tests voor scripts/_sweepstate.py - watermark + transcript-reader."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _sweepstate as ss  # noqa: E402


class SweepStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sweep-"))
        self.vault = self.tmp / "vault"
        self.tdir = self.vault / "01-raw" / "transcripts"
        self.tdir.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _t(self, name, records):
        p = self.tdir / name
        p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return p

    def test_pending_excludes_marked(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self._t("b.jsonl", [{"type": "user", "message": {"role": "user", "content": "hoi"}}])
        self.assertEqual({p.stem for p in ss.pending()}, {"a", "b"})
        ss.mark(["a"])
        self.assertEqual({p.stem for p in ss.pending()}, {"b"})

    def test_mark_is_idempotent(self):
        self._t("a.jsonl", [{"type": "user", "message": {"role": "user", "content": "x"}}])
        ss.mark(["a"])
        ss.mark(["a"])
        self.assertEqual(ss.pending(), [])

    def test_transcript_text_reduces_messages(self):
        p = self._t("c.jsonl", [
            {"type": "user", "message": {"role": "user", "content": "Repareer de bug"}},
            {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "text", "text": "Token-expiry fix"}]}},
        ])
        txt = ss.transcript_text(p)
        self.assertIn("Repareer de bug", txt)
        self.assertIn("Token-expiry fix", txt)

    def test_transcript_text_failsoft(self):
        bad = self.tdir / "bad.jsonl"
        bad.write_text("{ kapot json", encoding="utf-8")
        self.assertEqual(ss.transcript_text(bad), "")

    def test_block_text_none_content(self):
        """COVERAGE: _block_text(None) → lege string."""
        self.assertEqual(ss._block_text(None), "")

    def test_block_text_mixed_list_only_text_extracted(self):
        """COVERAGE: gemengde content-lijst → alleen text-blokken worden geëxtraheerd."""
        content = [
            {"type": "tool_use", "id": "some-tool-id"},
            {"type": "text", "text": "hello"},
            {"type": "image", "source": {"type": "base64", "data": "..."}},
            {"type": "text", "text": "world"},
        ]
        result = ss._block_text(content)
        self.assertIn("hello", result)
        self.assertIn("world", result)
        # Niet-tekst-blokken mogen NIET in de output belanden
        self.assertNotIn("tool_use", result)
        self.assertNotIn("base64", result)


if __name__ == "__main__":
    unittest.main()


class SweepLockOwnershipTest(unittest.TestCase):
    """De sweep-lock als bezit, niet als leeftijdsstempel.

    Twee defecten die deze tests bewaken, beide gevonden in review nadat de
    lease-versie al gemerged was:

    1. run_sweep startte onvoorwaardelijk een lease en gaf het slot
       onvoorwaardelijk vrij, ook als het proces het nooit verwierf. Er zijn
       drie aanroepers en twee daarvan slaan sweep-launch over
       (commands/kennisbank/rebuild-memory.md, scripts/index-launch.py), dus
       die verwijderden het slot van een sweep die nog draaide.
    2. De lease tikte door zolang het proces leefde. Een vastgelopen sweep hield
       daarmee zijn slot voor onbepaalde tijd, waar de oude leeftijdslogica na
       STALE_SEC vanzelf herstelde.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-lock-"))
        (self.tmp / ".claude").mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tweede_verwerving_faalt_en_release_geeft_vrij(self):
        tok = ss.acquire_lock(self.tmp)
        self.assertIsNotNone(tok)
        self.assertIsNone(ss.acquire_lock(self.tmp), "single-flight")
        self.assertTrue(ss.release_lock(self.tmp, tok))
        self.assertIsNotNone(ss.acquire_lock(self.tmp), "na vrijgave weer te nemen")

    def test_release_verwijdert_het_slot_van_een_ander_niet(self):
        """De regressie. Een sweep die het slot nooit nam mag het niet weggooien."""
        eigenaar = ss.acquire_lock(self.tmp)
        vreemde = "999999:deadbeefdeadbeef"
        self.assertFalse(ss.release_lock(self.tmp, vreemde),
                         "een vreemd token mag niets vrijgeven")
        self.assertTrue(ss.lock_path(self.tmp).exists(),
                        "het slot van de eigenaar staat er nog")
        self.assertTrue(ss.release_lock(self.tmp, eigenaar))

    def test_stale_lock_wordt_heroverd(self):
        ss.acquire_lock(self.tmp)
        lock = ss.lock_path(self.tmp)
        oud = time.time() - ss.STALE_SEC - 10
        os.utime(lock, (oud, oud))
        self.assertIsNotNone(ss.acquire_lock(self.tmp), "verweesd slot is herbruikbaar")

    def test_context_manager_geeft_altijd_vrij(self):
        """Elke vroege return en elke exception moet door de finally lopen."""
        with ss.sweep_lock(self.tmp) as owned:
            self.assertTrue(owned)
            self.assertTrue(ss.lock_path(self.tmp).exists())
        self.assertFalse(ss.lock_path(self.tmp).exists(), "vrijgegeven bij nette exit")

        with self.assertRaises(RuntimeError):
            with ss.sweep_lock(self.tmp) as owned:
                self.assertTrue(owned)
                raise RuntimeError("boem")
        self.assertFalse(ss.lock_path(self.tmp).exists(),
                         "ook vrijgegeven na een exception")

    def test_tweede_sweep_krijgt_false_en_raakt_het_slot_niet(self):
        buiten = ss.acquire_lock(self.tmp)
        with ss.sweep_lock(self.tmp) as owned:
            self.assertFalse(owned, "er draait al een sweep")
        self.assertEqual(ss._read_token(ss.lock_path(self.tmp)), buiten,
                         "het slot is nog van de eerste houder")

    def test_lease_houdt_het_slot_levend(self):
        origineel = ss.LEASE_REFRESH_SEC
        ss.LEASE_REFRESH_SEC = 0.05
        try:
            with ss.sweep_lock(self.tmp) as owned:
                self.assertTrue(owned)
                lock = ss.lock_path(self.tmp)
                oud = time.time() - ss.STALE_SEC - 600
                os.utime(lock, (oud, oud))
                self.assertTrue(ss.is_stale(lock), "opzet: nu is hij stale")
                deadline = time.time() + 5
                while time.time() < deadline and ss.is_stale(lock):
                    time.sleep(0.05)
                self.assertFalse(ss.is_stale(lock),
                                 "een draaiende sweep houdt zijn slot")
        finally:
            ss.LEASE_REFRESH_SEC = origineel

    def test_lease_stopt_bij_het_plafond(self):
        """Een tikkende thread bewijst dat het proces leeft, niet dat er voortgang is."""
        r, m = ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC
        ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC = 0.05, 0.15
        try:
            with ss.sweep_lock(self.tmp):
                lock = ss.lock_path(self.tmp)
                time.sleep(0.5)          # ruim voorbij het plafond
                gestopt = lock.stat().st_mtime
                time.sleep(0.4)
                self.assertEqual(lock.stat().st_mtime, gestopt,
                                 "voorbij het plafond mag de lease niet meer tikken")
        finally:
            ss.LEASE_REFRESH_SEC, ss.LEASE_MAX_SEC = r, m

    def test_lease_volgt_geen_gewijzigde_vault(self):
        """De thread bindt het vault-pad een keer.

        Resolveerde hij vault_root() per tik, dan schreef een thread die een test
        overleeft daarna in de vault waar KENNISBANK_VAULT naartoe is hersteld.
        Gemeten gedrag van de vorige versie; de tests gebruiken juist een
        tijdelijke vault om productie nooit te raken.
        """
        ander = Path(tempfile.mkdtemp(prefix="kb-ander-"))
        (ander / ".claude").mkdir(parents=True)
        origineel = ss.LEASE_REFRESH_SEC
        ss.LEASE_REFRESH_SEC = 0.05
        bewaard = os.environ.get("KENNISBANK_VAULT")
        try:
            with ss.sweep_lock(self.tmp):
                os.environ["KENNISBANK_VAULT"] = str(ander)
                time.sleep(0.4)
                self.assertFalse((ander / ".claude" / ss.LOCK_NAME).exists(),
                                 "de lease hoort bij de vault waar hij begon")
        finally:
            ss.LEASE_REFRESH_SEC = origineel
            if bewaard is None:
                os.environ.pop("KENNISBANK_VAULT", None)
            else:
                os.environ["KENNISBANK_VAULT"] = bewaard
            import shutil
            shutil.rmtree(ander, ignore_errors=True)
