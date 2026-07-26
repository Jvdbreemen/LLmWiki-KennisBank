"""De drift-check mag geen netwerk raken op de sessiestart-weg.

Kern van dit bestand: main() is de kant die de gebruiker laat wachten, en daar
hoort geen fetch. Gemeten op 2026-07-25 kostte de fetch 801 ms van de 1384 ms
(58%), en bij een trage verbinding loopt hij door tot FETCH_TIMEOUT -- waarmee
een startup-doel alleen nog geldt bij goed weer.

De fetch woont nu in refresh_remote(), die de losgekoppelde worker draait. Deze
tests leggen die scheiding vast, want ze is met een enkele regel weer ongedaan
te maken en dat zou niemand merken tot iemand in een trein zit.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


class GitProbe:
    """Vervangt _git en onthoudt welke subcommando's zijn aangeroepen."""

    def __init__(self, antwoorden: dict):
        self.antwoorden = antwoorden
        self.calls: list[tuple] = []

    def __call__(self, *args, timeout=5.0):
        self.calls.append(args)
        for sleutel, waarde in self.antwoorden.items():
            if args[:len(sleutel)] == sleutel:
                return waarde
        return None

    @property
    def subcommandos(self) -> list:
        return [a[0] for a in self.calls if a]


BASIS = {
    ("rev-parse", "--is-inside-work-tree"): "true",
    ("rev-parse", "--abbrev-ref", "HEAD"): "feature/x",
    ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/feature/x",
    ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "main@{upstream}"): "origin/main",
    ("status",): "",
    ("-c",): "",
    ("rev-list",): "0",
}


class DriftCheckTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("git-upstream-check.py")

    def _patch(self, antwoorden=None):
        probe = GitProbe(dict(antwoorden or BASIS))
        self.mod._git = probe
        return probe

    # --- de invariant --------------------------------------------------------

    def test_main_doet_geen_fetch(self):
        """De enige regel die er echt toe doet."""
        probe = self._patch()
        self.mod.main()
        self.assertNotIn("fetch", probe.subcommandos,
                         f"netwerk op de sessiestart-weg: {probe.calls}")

    def test_main_telt_nog_wel_de_drift(self):
        """Zonder fetch moeten de tellingen blijven werken -- ze lezen de object
        store die de vorige achtergrondrun heeft bijgewerkt."""
        probe = self._patch()
        self.mod.main()
        self.assertIn("rev-list", probe.subcommandos)

    def test_main_meldt_achterstand(self):
        antwoorden = dict(BASIS)
        antwoorden[("rev-list",)] = "3"
        self._patch(antwoorden)
        import io
        buf, oud = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            self.mod.main()
        finally:
            sys.stdout = oud
        self.assertIn("3 commit(s) achter", buf.getvalue())

    # --- de verhuisde kant ---------------------------------------------------

    def test_refresh_remote_doet_wel_een_fetch(self):
        probe = self._patch()
        self.mod.refresh_remote()
        self.assertIn("fetch", probe.subcommandos)

    def test_refresh_remote_kiest_de_remote_uit_de_upstream_ref(self):
        antwoorden = dict(BASIS)
        antwoorden[("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")] = "fork/feature/x"
        probe = self._patch(antwoorden)
        self.mod.refresh_remote()
        fetch = next(a for a in probe.calls if a and a[0] == "fetch")
        self.assertIn("fork", fetch)

    def test_refresh_remote_zwijgt_buiten_een_repo(self):
        probe = self._patch({("rev-parse", "--is-inside-work-tree"): "false"})
        self.assertFalse(self.mod.refresh_remote())
        self.assertNotIn("fetch", probe.subcommandos)

    def test_refresh_remote_zonder_upstream_doet_niets(self):
        antwoorden = dict(BASIS)
        for k in (("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
                  ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "main@{upstream}")):
            antwoorden[k] = None
        probe = self._patch(antwoorden)
        self.assertFalse(self.mod.refresh_remote())
        self.assertNotIn("fetch", probe.subcommandos)

    def test_fetch_krijgt_de_eigen_timeout(self):
        """FETCH_TIMEOUT bestaat om een dode verbinding te begrenzen; hij moet
        ook echt meegegeven worden en niet terugvallen op de default van _git."""
        gezien = {}

        def nep(*args, timeout=5.0):
            if args and args[0] == "fetch":
                gezien["timeout"] = timeout
                return ""
            return GitProbe(dict(BASIS))(*args, timeout=timeout)

        self.mod._git = nep
        self.mod.refresh_remote()
        self.assertEqual(gezien.get("timeout"), self.mod.FETCH_TIMEOUT)


class AchtergrondjobTest(unittest.TestCase):
    def test_job_staat_in_de_worker(self):
        """De fetch is alleen echt verhuisd als iemand hem ook draait."""
        il = load_script("index-launch.py")
        self.assertIn("git-fetch-refresh.py", [s for s, _ in il.JOBS])

    def test_job_script_bestaat_en_roept_refresh_remote_aan(self):
        scripts = Path(__file__).resolve().parent.parent / "scripts"
        self.assertTrue((scripts / "git-fetch-refresh.py").exists())
        bron = (scripts / "git-fetch-refresh.py").read_text(encoding="utf-8")
        self.assertIn("refresh_remote", bron)

    def test_stale_venster_groeit_mee_met_de_extra_job(self):
        """STALE_SEC is afgeleid van len(JOBS). Een job erbij zonder dat het
        venster meegroeit, laat een tweede worker een draaiende eerste voor
        verweesd aanzien."""
        il = load_script("index-launch.py")
        self.assertGreaterEqual(il.STALE_SEC, il.PER_JOB_TIMEOUT * len(il.JOBS))


if __name__ == "__main__":
    unittest.main()
