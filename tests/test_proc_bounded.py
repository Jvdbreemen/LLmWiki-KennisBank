"""Het tijdbudget van run_bounded moet echt binden.

De regressie die dit voorkomt is gemeten, niet bedacht: subprocess.run met
timeout=120 leverde een test van 393 seconden op, omdat een kleinkind de
stdout-pijp openhield en communicate() daarop bleef wachten.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _proc import run_bounded  # noqa: E402

BASH = shutil.which("bash")

#: Ouder is snel klaar, kleinkind leeft door en heeft de uitvoer geerfd.
KLEINKIND = '''
python3 -c "import time; time.sleep(30)" &
sleep 0.2
echo "ouder klaar, kleinkind leeft nog"
'''

#: Ouder hangt zelf. Hier MOET het budget binden.
HANGT = '''
python3 -c "import time; time.sleep(30)" &
sleep 30
'''


class RunBoundedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-proctest-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gewone_run_geeft_output_en_returncode(self):
        r = run_bounded([sys.executable, "-c", "print('hallo')"], timeout=60)
        self.assertIn("hallo", r.output)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(r.timed_out)

    def test_stderr_komt_mee(self):
        r = run_bounded(
            [sys.executable, "-c", "import sys; sys.stderr.write('stuk')"],
            timeout=60)
        self.assertIn("stuk", r.output)

    def test_exitcode_blijft_leesbaar(self):
        # doctor.sh geeft 1 terug zodra er een FAIL is; die betekenis mag niet
        # verloren gaan in de helper.
        r = run_bounded([sys.executable, "-c", "raise SystemExit(1)"], timeout=60)
        self.assertEqual(r.returncode, 1)

    def test_budget_bindt_ook_zonder_kleinkinderen(self):
        begin = time.monotonic()
        r = run_bounded([sys.executable, "-c", "import time; time.sleep(30)"],
                        timeout=2)
        self.assertTrue(r.timed_out)
        self.assertLess(time.monotonic() - begin, 15,
                        "de timeout hield het proces niet tegen")

    @unittest.skipIf(BASH is None, "bash niet beschikbaar")
    def test_een_kleinkind_houdt_de_aanroeper_niet_meer_vast(self):
        """De eigenlijke regressie, en het bewijs dat de aanpak klopt.

        Met subprocess.run duurde dit 25 s op een budget van 3: het kleinkind
        erfde de stdout-PIJP en communicate() wachtte daarop. Nu schrijft de
        ouder naar een BESTAND, dus zodra bash zelf klaar is (0,2 s) zijn wij
        ook klaar. Er is geen timeout meer nodig om eronderuit te komen.
        """
        script = self.tmp / "kleinkind.sh"
        script.write_text(KLEINKIND, encoding="utf-8")
        begin = time.monotonic()
        r = run_bounded([BASH, str(script)], timeout=20)
        verstreken = time.monotonic() - begin
        self.assertFalse(r.timed_out,
                         "de ouder was klaar; dit hoort geen timeout te zijn")
        self.assertIn("ouder klaar", r.output)
        self.assertLess(verstreken, 15,
                        f"een kleinkind van 30 s hield de aanroeper "
                        f"{verstreken:.1f}s vast")

    @unittest.skipIf(BASH is None, "bash niet beschikbaar")
    def test_een_hangende_ouder_wordt_wel_afgekapt(self):
        """De andere helft: hangt de OUDER, dan moet het budget wel binden."""
        script = self.tmp / "hangt.sh"
        script.write_text(HANGT, encoding="utf-8")
        begin = time.monotonic()
        r = run_bounded([BASH, str(script)], timeout=3)
        verstreken = time.monotonic() - begin
        self.assertTrue(r.timed_out)
        self.assertLess(verstreken, 15,
                        f"budget was 3s, werkelijk {verstreken:.1f}s")

    def test_output_tot_het_afkappunt_blijft_bewaard(self):
        # Een test die afkapt wil zien hoe ver het kwam; lege output maakt de
        # foutmelding onbruikbaar.
        r = run_bounded(
            [sys.executable, "-u", "-c",
             "print('begonnen', flush=True); import time; time.sleep(30)"],
            timeout=2)
        self.assertTrue(r.timed_out)
        self.assertIn("begonnen", r.output)

    def test_cwd_en_env_worden_doorgegeven(self):
        r = run_bounded(
            [sys.executable, "-c",
             "import os; print(os.environ.get('KB_PROBE', ''))"],
            cwd=str(self.tmp), env={**os.environ, "KB_PROBE": "42"}, timeout=60)
        self.assertIn("42", r.output)


if __name__ == "__main__":
    unittest.main()
