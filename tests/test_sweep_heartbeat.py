"""What the status file says after a sweep that did not reach its own end.

TASK-246. The sweep wrote memory-sweep-status.json only on its terminal paths,
so a run that was killed mid-loop left the previous status untouched and every
counter reading zero. Measured in the Kluis vault on 2026-09-09: the .swept
watermark held 418 stems, 170 memory files had been written in the preceding 36
hours, and the status reported processed 0. Two runs that had done real work
were read as failures on that evidence.

The fix is a partial heartbeat after each transcript. These tests pin the four
properties that make it worth having: it lands per transcript, it says whether
the run finished, it does not pay for the rot corpus scan on the way, and it
cannot leave a truncated file behind when the kill lands during the write.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "memory-sweep.py"
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("memory_sweep_heartbeat", str(SCRIPT))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Killed(BaseException):
    """Stands in for the harness killing the worker.

    A BaseException on purpose: the loop catches Exception per transcript, so an
    ordinary error is absorbed and never reproduces a kill.
    """


class HeartbeatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-heartbeat-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.m = _load()
        self.hb = self.vault / ".claude" / self.m.HEARTBEAT
        # extract_candidates hangt in de GEDEELDE module uit sys.modules; zonder
        # herstel erft de rest van de suite een extractor die niets vindt.
        self._orig_extract = self.m._extract.extract_candidates
        self.addCleanup(lambda: setattr(self.m._extract, "extract_candidates",
                                        self._orig_extract))
        self.m._model_reachable = lambda: True

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _transcript(self, name: str):
        line = json.dumps({"message": {"role": "user",
                                       "content": [{"type": "text", "text": "x" * 400}]}})
        p = self.vault / "01-raw" / "transcripts" / name
        p.write_text(line + "\n", encoding="utf-8")
        return p

    def _status(self) -> dict:
        return json.loads(self.hb.read_text(encoding="utf-8"))

    def _die_on_nth(self, n: int):
        """Extractor die bij de n-de aanroep een kill nabootst."""
        calls = {"n": 0}

        def extract(text, max_n=8):
            calls["n"] += 1
            if calls["n"] >= n:
                raise Killed("worker killed")
            return []
        self.m._extract.extract_candidates = extract

    # -- de kernclaim -------------------------------------------------------

    def test_a_killed_run_reports_the_transcripts_it_already_did(self):
        """Dit faalde voor TASK-246: de status bleef op de vorige run staan."""
        for i in range(4):
            self._transcript("2026-09-09-t%d.jsonl" % i)
        self._die_on_nth(3)

        with self.assertRaises(Killed):
            self.m.run_sweep()

        s = self._status()
        self.assertEqual(s["processed"], 2,
                         "twee transcripts waren af voordat de kill viel")
        self.assertTrue(s["running"],
                        "een afgebroken run mag zich niet als afgerond melden")

    def test_a_killed_run_reports_what_is_still_waiting(self):
        """pending_left nul bij een dode run leest als klaar."""
        for i in range(4):
            self._transcript("2026-09-09-t%d.jsonl" % i)
        self._die_on_nth(2)

        with self.assertRaises(Killed):
            self.m.run_sweep()

        # Het transcript waarop de kill viel telt mee als afgehandeld: het
        # watermark-gedrag daarvoor is ongewijzigd, alleen de telling is nu
        # zichtbaar. Twee van de vier zijn nog niet aangeraakt.
        self.assertEqual(self._status()["pending_left"], 2)

    def test_a_finished_run_says_it_finished(self):
        for i in range(2):
            self._transcript("2026-09-09-t%d.jsonl" % i)
        self.m._extract.extract_candidates = lambda text, max_n=8: []

        self.m.run_sweep()

        s = self._status()
        self.assertFalse(s["running"], "afgeronde run moet running False melden")
        self.assertEqual(s["processed"], 2)
        self.assertEqual(s["pending_left"], 0)

    # -- de tussenstand mag niets kosten en niets weggooien ------------------

    def test_the_partial_write_skips_the_rot_scan_and_keeps_the_previous_counts(self):
        """De rot-telling is een corpusscan over duizenden bestanden.

        Hij hangt niet aan het transcript dat net af is, dus per transcript
        opnieuw tellen is pure kosten. Wat memory-notify leest moet wel blijven
        staan, anders verdwijnt de melding zodra een run wordt afgebroken.
        """
        for i in range(3):
            self._transcript("2026-09-09-t%d.jsonl" % i)
        self.hb.write_text(json.dumps({
            "rot": 297, "rot_hours": 48, "rot_waiting": 278, "rot_undecided": 19,
        }), encoding="utf-8")
        scans = {"n": 0}

        def counted():
            scans["n"] += 1
            return {"total": 1, "waiting": 1, "undecided": 0}
        self.m._rot_breakdown = counted
        self._die_on_nth(3)

        with self.assertRaises(Killed):
            self.m.run_sweep()

        self.assertEqual(scans["n"], 0,
                         "een tussenstand mag het corpus niet opnieuw scannen")
        s = self._status()
        # Eerst bewijzen DAT er een tussenstand geland is. Zonder deze regel
        # slaagt de test ook op de oude implementatie, die simpelweg niets
        # schreef: nul scans en de ingezaaide waarden nog intact.
        self.assertEqual(s["processed"], 2, "er is geen tussenstand geschreven")
        self.assertEqual(s["rot_waiting"], 278, "vorige telling moet blijven staan")
        self.assertEqual(s["rot_undecided"], 19)

    def test_the_end_of_a_run_does_count_the_rot(self):
        """Het tegenovergestelde bewijs: overslaan mag alleen op de tussenstand."""
        self._transcript("2026-09-09-t0.jsonl")
        self.m._extract.extract_candidates = lambda text, max_n=8: []
        self.m._rot_breakdown = lambda: {"total": 7, "waiting": 5, "undecided": 2}

        self.m.run_sweep()

        s = self._status()
        self.assertEqual(s["rot"], 7)
        self.assertEqual(s["rot_waiting"], 5)

    # -- een kill tijdens het schrijven zelf --------------------------------

    def test_a_failed_write_leaves_the_previous_status_readable(self):
        """De tussenstand valt nu tijdens de run, dus een kill kan hem raken.

        In-place schrijven laat dan een half bestand achter en json.loads faalt:
        de lezer ziet niets meer in plaats van iets ouds. Schrijven via een tmp
        plus os.replace houdt de vorige stand heel.
        """
        before = {"processed": 41, "written": 42, "running": False}
        self.hb.write_text(json.dumps(before), encoding="utf-8")
        real_replace = os.replace

        def failing_replace(src, dst):
            raise OSError("kill tijdens replace")
        os.replace = failing_replace
        try:
            self.m._write_heartbeat({"processed": 1, "written": 1})
        finally:
            os.replace = real_replace

        self.assertEqual(self._status(), before,
                         "de oude status is overschreven of afgekapt")
        leftovers = list((self.vault / ".claude").glob(self.m.HEARTBEAT + ".*.tmp"))
        self.assertEqual(leftovers, [], "tmp-bestand blijft achter")


if __name__ == "__main__":
    unittest.main()
