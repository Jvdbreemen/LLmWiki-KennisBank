"""De fan-out van de sessie-coordinatoren is begrensd door de machine.

De drie coordinatoren gebruikten `max_workers=len(jobs)`. Dat schaalt de pool
mee met het WERK in plaats van met de MACHINE: elke job start een echte
Python-interpreter, dus een zesde indexbouwer betekent zes interpreters die op
hetzelfde moment beginnen, ongeacht waar dat draait. Op een desktop met zestien
cores valt dat niet op. Op een tweecore-laptop of in een CI-container met een
fractionele CPU-quota is het het verschil tussen een achtergrondklusje en een
machine die even niet meer reageert.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import POOL_HEADROOM, pool_workers  # noqa: E402


class PoolWorkersTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("KB_MAX_WORKERS", None)

    def tearDown(self):
        os.environ.pop("KB_MAX_WORKERS", None)
        if self._saved is not None:
            os.environ["KB_MAX_WORKERS"] = self._saved

    def test_nooit_meer_workers_dan_jobs(self):
        for n in (1, 2, 3, 5):
            self.assertLessEqual(pool_workers(n), n)

    def test_laat_cores_vrij_voor_de_gebruiker(self):
        cores = os.cpu_count() or 4
        # Een fan-out die groter is dan de machine moet op de machine landen,
        # met ruimte over: een hook draait terwijl iemand doorwerkt.
        self.assertLessEqual(pool_workers(cores * 4), max(2, cores - POOL_HEADROOM))

    def test_blijft_een_fan_out_op_een_kleine_machine(self):
        # Ondergrens 2: met een pool van 1 is de coordinator geen coordinator
        # meer maar een for-lus, en de trage job blokkeert alle snelle.
        self.assertGreaterEqual(pool_workers(4), 2)

    def test_leeg_werk_vraagt_geen_pool(self):
        self.assertEqual(pool_workers(0), 1)
        self.assertEqual(pool_workers(-3), 1)

    def test_operator_mag_overrulen(self):
        # De reden dat deze knop bestaat: os.cpu_count() ziet de cgroup-quota
        # van een container niet, dus daar weet de operator het beter.
        os.environ["KB_MAX_WORKERS"] = "1"
        self.assertEqual(pool_workers(5), 1)
        os.environ["KB_MAX_WORKERS"] = "2"
        self.assertEqual(pool_workers(5), 2)

    def test_onzin_in_de_knop_valt_terug_op_de_machine(self):
        os.environ["KB_MAX_WORKERS"] = "veel"
        self.assertEqual(pool_workers(5), min(5, max(2, (os.cpu_count() or 4) - POOL_HEADROOM)))


def _load(naam: str):
    spec = importlib.util.spec_from_file_location(
        naam.replace("-", "_"), SCRIPTS / f"{naam}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CoordinatorRespecteertDeCapTest(unittest.TestCase):
    """De cap moet in de echte pool zitten, niet alleen in de helper."""

    def setUp(self):
        self._saved = os.environ.get("KB_MAX_WORKERS")
        os.environ["KB_MAX_WORKERS"] = "2"

    def tearDown(self):
        os.environ.pop("KB_MAX_WORKERS", None)
        if self._saved is not None:
            os.environ["KB_MAX_WORKERS"] = self._saved

    def test_niet_meer_dan_twee_indexjobs_tegelijk(self):
        module = _load("kb-session-log")
        self.assertGreater(len(module.INDEX_JOBS), 2,
                           "opzet: er moeten meer jobs zijn dan de cap toestaat")
        lock = threading.Lock()
        tegelijk = 0
        piek = 0
        klaar = threading.Event()

        def runner(job, _scripts):
            nonlocal tegelijk, piek
            if job in module.INDEX_JOBS:
                with lock:
                    tegelijk += 1
                    piek = max(piek, tegelijk)
                    if piek >= 2:
                        klaar.set()
                # Houd de job vast tot de pool zo breed is als hij mag worden,
                # zodat een te ruime pool zich niet achter snelle jobs verstopt.
                klaar.wait(30)
                with lock:
                    tegelijk -= 1
            return module.Result(job.script)

        module.run_parallel(module.INDEX_JOBS, Path("."), runner=runner)
        self.assertEqual(piek, 2, f"pool werd {piek} breed terwijl de cap 2 is")


if __name__ == "__main__":
    unittest.main()
