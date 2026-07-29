"""Tests voor scripts/kb-normalize.py — deterministische post-pass (TASK-90 E3).

De harde eisen: idempotent (twee runs = byte-identiek), vorm-normalisatie
zonder inhoudsmutatie, en de llm_wiki #576-fixture (padgeprefixte links na
een merge) wordt gerepareerd terwijl 05-bronnen-paden intact blijven.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._loader import load_script


def _kn():
    return load_script("kb-normalize.py")


class NormalizeLinkTest(unittest.TestCase):
    def setUp(self):
        self.kn = _kn()

    def test_576_fixture_path_prefixed_link_reduced_to_stem(self):
        self.assertEqual(self.kn.normalize_link_inner("clients/foo-overview"),
                         "foo-overview")
        self.assertEqual(self.kn.normalize_link_inner("01-raw/sessies/raw-sessie-x.md"),
                         "raw-sessie-x")

    def test_alias_and_anchor_preserved(self):
        self.assertEqual(self.kn.normalize_link_inner("pad/naar/doc.md#kop|alias"),
                         "doc#kop|alias")

    def test_bronnen_prefix_kept(self):
        self.assertEqual(self.kn.normalize_link_inner("05-bronnen/import/nota.md"),
                         "05-bronnen/import/nota.md")

    def test_backslashes_normalized(self):
        self.assertEqual(self.kn.normalize_link_inner("pad\\naar\\doc.md"), "doc")

    def test_bare_stem_untouched(self):
        self.assertEqual(self.kn.normalize_link_inner("raw-sessie-x|bron"),
                         "raw-sessie-x|bron")


class NormalizeTextTest(unittest.TestCase):
    def setUp(self):
        self.kn = _kn()
        self.doc = ("---\ntitle: T\ntags: vpn, netwerk\nstatus: actief\n---\n\n"
                    "Zie [[clients/foo-overview.md|foo]] en [[05-bronnen/x.md]].\n\n"
                    "## Sessie-herkomst\n- punt: [[01-raw/sessies/raw-sessie-a.md]]\n")

    def test_normalizes_links_and_tags(self):
        out = self.kn.normalize_text(self.doc)
        self.assertIn("[[foo-overview|foo]]", out)
        self.assertIn("[[05-bronnen/x.md]]", out)
        self.assertIn("[[raw-sessie-a]]", out)
        self.assertIn("tags: [vpn, netwerk]", out)

    def test_idempotent(self):
        once = self.kn.normalize_text(self.doc)
        self.assertEqual(self.kn.normalize_text(once), once)

    def test_clean_doc_byte_identical(self):
        clean = ("---\ntitle: T\ntags: [a]\n---\n\nTekst met [[raw-sessie-a]].\n")
        self.assertEqual(self.kn.normalize_text(clean), clean)

    def test_frontmatter_links_untouched(self):
        doc = ('---\ntitle: T\nsuperseded_by: ["[[pad/naar/x]]"]\ntags: []\n---\n\nB.\n')
        self.assertEqual(self.kn.normalize_text(doc), doc)

    def test_body_prose_untouched(self):
        out = self.kn.normalize_text(self.doc)
        self.assertIn("## Sessie-herkomst", out)
        self.assertIn("Zie ", out)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.kn = _kn()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Path(self.tmp.name) / "a.md"
        self.f.write_text("Tekst [[pad/doc.md]].\n", encoding="utf-8")

    def test_check_mode_exits_2_and_writes_nothing(self):
        before = self.f.read_text(encoding="utf-8")
        rc = self.kn.main([str(self.f), "--check"])
        self.assertEqual(rc, 2)
        self.assertEqual(self.f.read_text(encoding="utf-8"), before)

    def test_write_mode_normalizes_then_clean(self):
        self.assertEqual(self.kn.main([str(self.f)]), 0)
        self.assertIn("[[doc]]", self.f.read_text(encoding="utf-8"))
        self.assertEqual(self.kn.main([str(self.f), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
