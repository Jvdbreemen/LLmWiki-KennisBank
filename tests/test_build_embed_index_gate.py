"""Gate-test voor build-embed-index.py op de embed_index toggle.

Met de toggle uit moet main() vroeg terugkeren ZONDER neveneffect. We bewijzen
dat via de graphify .needs-rebuild-flag: main() leegt die normaal, dus als de
flag na een run nog bestaat is main() ervoor afgehaakt. Geen embedding-backend
nodig: de gate zit vóór elke embed-call.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


class EmbedIndexGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-embgate-"))
        self.vault = self.tmp / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "02-wiki" / "a.md").write_text("# a\ntekst", encoding="utf-8")
        self.rebuild = self.vault / "graphify-out" / ".needs-rebuild"
        self.rebuild.parent.mkdir(parents=True)
        self.rebuild.write_text("02-wiki/a.md\n", encoding="utf-8")
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gate_off_leaves_rebuild_flag(self):
        (self.vault / "kennisbank-settings.json").write_text(
            '{"embed_index": false}', encoding="utf-8")
        mod = load_script("build-embed-index.py")
        mod.main()
        self.assertTrue(self.rebuild.exists(),
                        "main() mag de flag niet legen als embed_index uit staat")

    def test_embed_run_never_touches_rebuild_flag(self):
        """De vlag hoort de embed-run te overleven, ook als die gewoon draait.

        Voorheen wiste main() hem onvoorwaardelijk, gegate op de ongerelateerde
        embed_index-toggle. Beide lezers (`/sessiestart` en de Atlas-sidecar)
        meldden daardoor altijd "niet stale" -- het staleness-signaal bestond in
        de praktijk niet. Deze test verving een test die precies het omgekeerde
        vastlegde.
        """
        before = self.rebuild.read_bytes()
        mod = load_script("build-embed-index.py")
        # Geen echte embed-backend nodig: get_cached faalt fail-soft en telt als
        # 'failed'. Het gaat hier alleen om wat main() met de vlag doet.
        mod.main()
        self.assertTrue(self.rebuild.exists(),
                        "embed-run heeft de graphify-rebuild-vlag gewist")
        self.assertEqual(self.rebuild.read_bytes(), before,
                         "embed-run heeft de vlag aangepast")


if __name__ == "__main__":
    unittest.main()
