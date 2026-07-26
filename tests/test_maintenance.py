"""Tests voor scripts/_maintenance.py - deterministische cross-memory-primitieven.
emb.get_cached wordt geinjecteerd (geen model). Vault naar temp.

Fixture-noot: de originele brief matched op single-char substrings ('a','b','c')
in de bestandsinhoud, die overal voorkomen in frontmatter (bijv. 'created',
'basis', 'cc-sessie'). Alle drie items krijgen dan vector [1,0,0] (first-match),
waardoor cosine-discriminatie niet echt getest wordt. Aangepast om op
bestandsnaam-suffix te matchen (-a.md/-b.md/-c.md), en assertions versterkt
zodat precies de juiste paren gevonden worden."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _maintenance as mnt  # noqa: E402
import _memory  # noqa: E402

# a en b liggen dicht bij elkaar (cosine ≈ 0.9998 > 0.9)
# c staat loodrecht op a/b (cosine = 0)
_VECS = {
    "a": [1.0, 0.0, 0.0],
    "b": [0.98, 0.02, 0.0],
    "c": [0.0, 1.0, 0.0],
}


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mnt-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        for name, created in (("a", "2026-06-01"), ("b", "2026-06-05"), ("c", "2026-06-03")):
            _memory.write(name, f"body van {name}", status="current", created=created)
        # de _memory.write maakt datum-geprefixte namen; pak de echte paden
        self.files = sorted((self.vault / "09-memory").glob("*.md"))

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_cache(self):
        # Match op bestandsnaam-suffix (-a.md/-b.md/-c.md) i.p.v. body-substring
        # zodat single-char-matches in frontmatter geen vals positief geven.
        def gc(path, cache, recompute=True):
            name = Path(path).name
            for stem, vec in _VECS.items():
                if name.endswith(f"-{stem}.md"):
                    return vec
            return [0.5, 0.5, 0.5]
        return gc

    def test_current_items_loaded(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        self.assertEqual(len(items), 3)
        self.assertTrue(all("vec" in it and "created" in it for it in items))

    def test_similar_pairs(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        pairs = mnt.similar_pairs(items, threshold=0.9)
        # a & b liggen dicht bij elkaar (cosine ≈ 0.9998); c is ver (cosine = 0)
        # precies 1 paar: (a, b)
        self.assertEqual(len(pairs), 1)
        pair_names = {Path(pairs[0][0]["path"]).name, Path(pairs[0][1]["path"]).name}
        self.assertTrue(any(n.endswith("-a.md") for n in pair_names))
        self.assertTrue(any(n.endswith("-b.md") for n in pair_names))

    def test_neighbor_counts(self):
        items = mnt.current_items(get_cached_fn=self._fake_cache())
        counts = mnt.neighbor_counts(items, threshold=0.9)
        # a en b hebben elk 1 buur; c heeft 0 buren; totaal = 2
        self.assertEqual(sum(counts.values()), 2)
        c_path = next(str(f) for f in (self.vault / "09-memory").glob("*-c.md"))
        self.assertEqual(counts[c_path], 0)


class MemorySetStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-ss-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_status_superseded_with_link(self):
        p = _memory.write("Oud", "iets ouds", status="current", created="2026-06-01")
        ok = _memory.set_status(p, "superseded", superseded_by=["2026-06-05-nieuw"])
        self.assertTrue(ok)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("status: superseded", txt)
        self.assertIn("[[2026-06-05-nieuw]]", txt)
        self.assertEqual(_memory.read_status(p), "superseded")


if __name__ == "__main__":
    unittest.main()


class ExactDuplicatePassTest(unittest.TestCase):
    """TASK-73: byte-identieke memories horen automatisch opgeruimd te worden.

    Los van supersede_pass, en met opzet zonder embeddings of judge: bij een
    identieke body valt er niets te oordelen, en een oordeel kan fout gaan.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-dup-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _schrijf(self, titel, body, created, status="current", **kw):
        p, _ = _memory.unique_memory_path(titel, created=created, body=None)
        p.write_text(_memory.render(titel, body, status=status, created=created, **kw),
                     encoding="utf-8")
        return p

    def _status(self, p):
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(Path(p).read_text(encoding="utf-8"))
        return fm.get("status"), fm.get("superseded_by")

    def test_identieke_bodies_worden_gesloten_op_een_na(self):
        a = self._schrijf("Eerste", "exact dezelfde inhoud", "2026-06-01")
        b = self._schrijf("Tweede", "exact dezelfde inhoud", "2026-06-05")
        n = mnt.exact_duplicate_pass()
        self.assertEqual(n, 1)
        self.assertEqual(self._status(a)[0], "current", "de oudste blijft open")
        st, link = self._status(b)
        self.assertEqual(st, "superseded")
        self.assertEqual(link, [f"[[{a.stem}]]"], "de link moet terugwijzen")

    def test_afwijkende_bodies_blijven_met_rust(self):
        a = self._schrijf("Eerste", "inhoud een", "2026-06-01")
        b = self._schrijf("Tweede", "inhoud twee", "2026-06-05")
        self.assertEqual(mnt.exact_duplicate_pass(), 0)
        self.assertEqual(self._status(a)[0], "current")
        self.assertEqual(self._status(b)[0], "current")

    def test_de_oudste_op_eventtijd_blijft_niet_de_oudste_op_capture(self):
        """valid_from is de event-tijd; created is wanneer we het opschreven.
        Een laat gecaptured OUD feit hoort de behoudene te zijn."""
        laat = self._schrijf("Laat opgeschreven", "zelfde", "2026-06-20",
                             valid_from="2026-01-01")
        vroeg = self._schrijf("Vroeg opgeschreven", "zelfde", "2026-06-02",
                              valid_from="2026-05-01")
        mnt.exact_duplicate_pass()
        self.assertEqual(self._status(laat)[0], "current")
        self.assertEqual(self._status(vroeg)[0], "superseded")

    def test_lege_bodies_tellen_niet_als_duplicaat(self):
        a = self._schrijf("Leeg een", "", "2026-06-01")
        b = self._schrijf("Leeg twee", "", "2026-06-02")
        self.assertEqual(mnt.exact_duplicate_pass(), 0)
        self.assertEqual(self._status(a)[0], "current")
        self.assertEqual(self._status(b)[0], "current")

    def test_gesloten_memories_doen_niet_mee(self):
        self._schrijf("Oud gesloten", "zelfde", "2026-06-01", status="superseded")
        b = self._schrijf("Open", "zelfde", "2026-06-05")
        self.assertEqual(mnt.exact_duplicate_pass(), 0)
        self.assertEqual(self._status(b)[0], "current")

    def test_unverified_telt_wel_mee(self):
        """Duplicaten stapelen zich juist op in de unverified-laag."""
        self._schrijf("Eerste", "zelfde", "2026-06-01", status="unverified")
        self._schrijf("Tweede", "zelfde", "2026-06-05", status="unverified")
        self.assertEqual(mnt.exact_duplicate_pass(), 1)

    def test_witruimte_maakt_geen_verschil(self):
        self._schrijf("Eerste", "inhoud", "2026-06-01")
        self._schrijf("Tweede", "  inhoud  ", "2026-06-05")
        self.assertEqual(mnt.exact_duplicate_pass(), 1)

    def test_dry_run_telt_maar_wijzigt_niets(self):
        self._schrijf("Eerste", "zelfde", "2026-06-01")
        b = self._schrijf("Tweede", "zelfde", "2026-06-05")
        self.assertEqual(mnt.exact_duplicate_pass(dry_run=True), 1)
        self.assertEqual(self._status(b)[0], "current", "dry_run mag niet schrijven")

    def test_idempotent(self):
        self._schrijf("Eerste", "zelfde", "2026-06-01")
        self._schrijf("Tweede", "zelfde", "2026-06-05")
        self.assertEqual(mnt.exact_duplicate_pass(), 1)
        self.assertEqual(mnt.exact_duplicate_pass(), 0, "tweede run doet niets")

    def test_drie_dubbelen_laten_er_een_over(self):
        for i, d in enumerate(("2026-06-01", "2026-06-05", "2026-06-09")):
            self._schrijf(f"Kopie {i}", "zelfde", d)
        self.assertEqual(mnt.exact_duplicate_pass(), 2)
        open_ = [p for p in (self.vault / "09-memory").glob("*.md")
                 if self._status(p)[0] == "current"]
        self.assertEqual(len(open_), 1)

    def test_omkeerbaar_niets_wordt_verwijderd(self):
        """AC #8: opruimen mag niets stilzwijgend laten verdwijnen."""
        self._schrijf("Eerste", "zelfde", "2026-06-01")
        self._schrijf("Tweede", "zelfde", "2026-06-05")
        voor = {p.name for p in (self.vault / "09-memory").glob("*.md")}
        mnt.exact_duplicate_pass()
        na = {p.name for p in (self.vault / "09-memory").glob("*.md")}
        self.assertEqual(voor, na, "geen enkel bestand mag verdwijnen")

    def test_herkomst_van_de_dubbel_blijft_bewaard(self):
        """AC #12: de gesloten dubbel houdt zijn eigen source_session."""
        from _frontmatter import parse_frontmatter
        self._schrijf("Eerste", "zelfde", "2026-06-01", source_session="sessie-a.jsonl")
        b = self._schrijf("Tweede", "zelfde", "2026-06-05", source_session="sessie-b.jsonl")
        mnt.exact_duplicate_pass()
        fm, _ = parse_frontmatter(b.read_text(encoding="utf-8"))
        self.assertEqual(fm.get("source_session"), "sessie-b.jsonl")

    def test_het_ongenummerde_bestand_blijft_niet_de_kopie(self):
        """Gemeten op de echte vault: sortering op pad hield consequent de
        DUBBEL. '-' sorteert voor '.', dus '...-resources-2.md' komt voor
        '...-resources.md'. Een -2 is per definitie de latere schrijver."""
        origineel = self.vault / "09-memory" / "2026-06-01-zelfde-onderwerp.md"
        kopie = self.vault / "09-memory" / "2026-06-01-zelfde-onderwerp-2.md"
        for p in (origineel, kopie):
            p.write_text(_memory.render("Zelfde onderwerp", "identieke inhoud",
                                        status="current", created="2026-06-01"),
                         encoding="utf-8")
        self.assertEqual(mnt.exact_duplicate_pass(), 1)
        self.assertEqual(self._status(origineel)[0], "current")
        self.assertEqual(self._status(kopie)[0], "superseded")
        self.assertEqual(self._status(kopie)[1], [f"[[{origineel.stem}]]"])
