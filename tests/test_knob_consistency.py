"""Knoppen moeten overeenkomen met hun bron (TASK-66).

Drie soorten drift die deze repo alledrie heeft gehad, en die geen enkele test
ving omdat elke plek op zichzelf klopte:

1. Een kalibratieharnas dat een drempel rapporteert die het bijbehorende script
   niet gebruikt. Het harnas meldde [OK] waar [HERIJK] hoorde te staan.
2. Een toggle in DEFAULTS die in geen van de beheeroppervlakken staat, zodat een
   gebruiker hem niet kan aan- of uitzetten. Vier lijsten, vier keer handmatig.
3. Een omgevingsvariabele die leeg gezet is en dan als relatief pad wordt
   uitgelegd, waarna installatie configuratie in de werkmap schrijft.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tests._loader import load_script  # noqa: E402


class CalibrationKnobsMatchTheirSourceTest(unittest.TestCase):
    """Het harnas mag geen drempel rapporteren die de code niet gebruikt."""

    def _knobs(self) -> dict:
        m = load_script("kb-calibrate.py")
        return {name: (value, kind) for name, value, kind in m.CURRENT_KNOBS}

    def test_rewrite_threshold_matches_find_similar(self):
        source = (SCRIPTS / "find-similar.py").read_text(encoding="utf-8")
        match = re.search(r"^\s*threshold\s*=\s*([0-9.]+)", source, re.M)
        self.assertIsNotNone(match, "find-similar.py heeft geen threshold-default meer")
        actual = float(match.group(1))
        reported, kind = self._knobs()["rewrite (find-similar)"]
        self.assertEqual(
            reported, actual,
            f"kb-calibrate rapporteert {reported} voor de rewrite-knop terwijl "
            f"find-similar.py {actual} gebruikt")
        self.assertEqual(kind, "related",
                         "0.62 ligt in de related-band, niet in de duplicate-band")

    def test_retrieve_threshold_matches_the_hook_default(self):
        source = (SCRIPTS / "kb-retrieve.py").read_text(encoding="utf-8")
        match = re.search(r'"retrieve_threshold",\s*([0-9.]+)', source)
        self.assertIsNotNone(match, "kb-retrieve.py heeft geen retrieve_threshold-default")
        reported, _ = self._knobs()["retrieve (retrieve_threshold)"]
        self.assertEqual(reported, float(match.group(1)))


class EverySettingIsManageableTest(unittest.TestCase):
    """Elke DEFAULTS-sleutel moet via de beheeroppervlakken te bereiken zijn.

    activity_llm_fallback stond wel in DEFAULTS maar in geen van de drie
    oppervlakken: een gebruiker kon hem niet vinden, laat staan omzetten.
    """

    SURFACES = (
        Path("commands/kennisbank/settings.md"),
        Path("skills/kennisbank-upgrade/SKILL.md"),
    )

    def test_every_default_key_appears_in_each_surface(self):
        import _settings
        missing = []
        for surface in self.SURFACES:
            text = (REPO_ROOT / surface).read_text(encoding="utf-8")
            for key in _settings.DEFAULTS:
                if key not in text:
                    missing.append(f"{surface}: {key}")
        self.assertEqual(
            missing, [],
            "toggles die in DEFAULTS staan maar niet in een beheeroppervlak; een "
            "gebruiker kan ze niet omzetten:\n  " + "\n  ".join(missing))


class EmptyAgentHomeFallsBackTest(unittest.TestCase):
    """Een leeg gezette agent-home mag geen relatief pad worden.

    os.environ.get(NAAM, default) springt NIET in bij een lege string, en het
    genormaliseerde pad wordt dan Path("."): installatie schrijft de config in
    de werkmap in plaats van in de agent-home.
    """

    VARS = ("CODEX_HOME", "OPENCODE_CONFIG_DIR", "COPILOT_HOME")

    def setUp(self):
        self._saved = {v: os.environ.get(v) for v in self.VARS}

    def tearDown(self):
        for var, val in self._saved.items():
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val

    def _assert_absolute_and_not_cwd(self, path, var):
        self.assertTrue(Path(path).is_absolute(),
                        f"{var} leeg -> relatief pad {path}")
        self.assertNotEqual(Path(path).resolve(), Path.cwd().resolve(),
                            f"{var} leeg -> config zou in de werkmap landen")

    def test_install_agent_envs_falls_back(self):
        m = load_script("install-agent-envs.py")
        for var, fn in (("CODEX_HOME", "_codex_home"),
                        ("OPENCODE_CONFIG_DIR", "_opencode_home")):
            with self.subTest(var=var):
                os.environ[var] = ""
                self._assert_absolute_and_not_cwd(getattr(m, fn)(), var)

    def test_copilot_falls_back(self):
        import _copilot
        os.environ["COPILOT_HOME"] = ""
        self._assert_absolute_and_not_cwd(_copilot.copilot_home(), "COPILOT_HOME")


if __name__ == "__main__":
    unittest.main()
