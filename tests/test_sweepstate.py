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


class SweepLockLeaseTest(unittest.TestCase):
    """De sweep-lock als lease in plaats van een leeftijdsstempel.

    De launcher nam de lock en niemand raakte hem daarna nog aan, terwijl de
    staleness-check in uren rekent. "Ouder dan STALE_SEC" betekende daardoor
    "de sweep draait al langer dan een uur", niet "de sweep is dood". Op een
    gegroeide vault haalt een sweep die drempel -- gemeten 23m52s voor een
    enkele onderhoudspass over 4077 memories -- en dan startte de volgende
    launcher een tweede sweep naast de eerste. Waargenomen: drie tegelijk.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-lease-"))
        (self.tmp / ".claude").mkdir(parents=True)
        ss._last_refresh = 0.0

    def tearDown(self):
        import shutil
        ss._last_refresh = 0.0
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _launcher(self):
        """sweep-launch.py laden, met zijn is_stale en STALE_SEC."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sweep_launch", str(SCRIPTS_DIR / "sweep-launch.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_refresh_touches_and_throttles(self):
        lock = ss.lock_path(self.tmp)
        self.assertTrue(ss.refresh_lock(self.tmp, now=1000.0))
        self.assertTrue(lock.exists())
        # Binnen het venster niet nog eens aanraken: de lease meet in uren, een
        # schrijfactie per chunk is pure I/O.
        self.assertFalse(ss.refresh_lock(self.tmp, now=1000.0 + ss.LOCK_REFRESH_SEC - 1))
        self.assertTrue(ss.refresh_lock(self.tmp, now=1000.0 + ss.LOCK_REFRESH_SEC))

    def test_een_lopende_sweep_verliest_zijn_slot_niet(self):
        """De regressie. Zonder lease was deze lock stale en spawnde de
        volgende launcher een tweede sweep."""
        launcher = self._launcher()
        lock = ss.lock_path(self.tmp)
        lock.write_text("123", encoding="utf-8")

        # Doe alsof de run al ruim over de stale-drempel loopt.
        oud = time.time() - (launcher.STALE_SEC + 600)
        os.utime(lock, (oud, oud))
        self.assertTrue(launcher.is_stale(lock), "opzet: zonder refresh is hij stale")

        # De sweep ververst zijn lease zoals hij dat op elke passgrens doet.
        self.assertTrue(ss.refresh_lock(self.tmp, now=time.time()))
        self.assertFalse(launcher.is_stale(lock),
                         "een sweep die nog werkt houdt zijn slot")

    def test_release_geeft_het_slot_direct_vrij(self):
        lock = ss.lock_path(self.tmp)
        ss.refresh_lock(self.tmp, now=time.time())
        self.assertTrue(lock.exists())
        ss.release_lock(self.tmp)
        self.assertFalse(lock.exists(),
                         "klaar is klaar; niet STALE_SEC laten liggen")
        ss.release_lock(self.tmp)  # tweede keer mag niet gooien

    def test_launcher_en_sweep_wijzen_naar_hetzelfde_bestand(self):
        launcher = self._launcher()
        self.assertEqual(launcher.LOCK_NAME, ss.LOCK_NAME)

    def test_lease_thread_dekt_ook_fases_zonder_grens(self):
        """Losse refresh-aanroepen dekten de looptijd niet.

        Gemeten op een echte run: de lock bleef 165 seconden op zijn starttijd
        staan terwijl de sweep werkte, omdat het inlezen van 4387 memories en
        de burenberekening in andere modules zitten en er dus geen lus- of
        passgrens is om een aanroep aan op te hangen. Een thread hangt niet aan
        de codestructuur en dekt daarom elke fase.
        """
        origineel = ss.LOCK_REFRESH_SEC
        ss.LOCK_REFRESH_SEC = 0.05
        try:
            lock = ss.lock_path(self.tmp)
            lock.write_text("x", encoding="utf-8")
            oud = time.time() - 3600
            os.utime(lock, (oud, oud))

            stop = ss.start_lease(self.tmp)
            try:
                deadline = time.time() + 5
                while time.time() < deadline:
                    if lock.stat().st_mtime > oud + 60:
                        break
                    time.sleep(0.05)
                self.assertGreater(lock.stat().st_mtime, oud + 60,
                                   "de thread heeft de lease niet ververst")
            finally:
                stop.set()

            # Na stop() staat de lease stil: dat is wat een dode sweep hoort te doen.
            time.sleep(0.2)
            na_stop = lock.stat().st_mtime
            time.sleep(0.3)
            self.assertEqual(lock.stat().st_mtime, na_stop,
                             "na stop() mag de lease niet meer bewegen")
        finally:
            ss.LOCK_REFRESH_SEC = origineel
