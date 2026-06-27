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
