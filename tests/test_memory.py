"""Tests voor scripts/_memory.py - het memory-format (frontmatter + paden).

Pure lib: geen netwerk, geen embeddings. Vault naar temp via KENNISBANK_VAULT.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _memory  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


class MemoryFormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-mem-"))
        self.vault = self.tmp / "vault"
        self.vault.mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

    def tearDown(self):
        import shutil
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_status_and_evidence_sets(self):
        self.assertEqual(
            _memory.STATUSES,
            ("unverified", "current", "superseded", "retracted", "expired"),
        )
        self.assertEqual(
            _memory.EVIDENCE_BASES,
            ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent"),
        )

    def test_memory_path_layout(self):
        p = _memory.memory_path("Hook-gedreven retrieval", created="2026-06-27")
        self.assertEqual(p.parent, self.vault / "09-memory")
        self.assertEqual(p.name, "2026-06-27-hook-gedreven-retrieval.md")

    def test_render_defaults_to_unverified(self):
        md = _memory.render("Titel", "De body.", created="2026-06-27", updated="2026-06-27")
        fm, body = parse_frontmatter(md)
        self.assertEqual(fm["type"], "memory")
        self.assertEqual(fm["status"], "unverified")
        self.assertEqual(fm["evidence_basis"], "cc-sessie")
        self.assertIn("De body.", body)

    def test_render_rejects_bad_status(self):
        with self.assertRaises(ValueError):
            _memory.render("T", "b", status="bogus")

    def test_render_rejects_bad_evidence_basis(self):
        with self.assertRaises(ValueError):
            _memory.render("T", "b", evidence_basis="hallucination")

    def test_write_creates_file_and_dir(self):
        p = _memory.write("Een les", "Wat ik leerde.", created="2026-06-27")
        self.assertTrue(p.exists())
        self.assertTrue((self.vault / "09-memory").is_dir())
        self.assertEqual(_memory.read_status(p), "unverified")

    def test_read_status_missing_returns_unverified(self):
        f = self.vault / "09-memory" / "x.md"
        f.parent.mkdir(parents=True)
        f.write_text("geen frontmatter", encoding="utf-8")
        self.assertEqual(_memory.read_status(f), "unverified")

    def test_render_sanitizes_quotes_and_newlines_in_title(self):
        md = _memory.render('Een "rare" titel\nmet newline', "body",
                            source_session='pad "met" quote', created="2026-06-27")
        # frontmatter moet pareerbaar blijven (geen kapotte YAML)
        fm, body = parse_frontmatter(md)
        self.assertEqual(fm.get("type"), "memory")
        self.assertNotIn("\n", fm.get("title", ""))   # newline weg
        self.assertIn("body", body)

    def test_render_tags_accepts_string(self):
        md = _memory.render("T", "b", tags="losse-string", created="2026-06-27")
        fm, _ = parse_frontmatter(md)
        self.assertEqual(fm.get("tags"), ["losse-string"])

    def test_render_superseded_by_accepts_string(self):
        # een enkele wikilink als string mag niet in characters uiteenvallen
        md = _memory.render("T", "b", superseded_by="[[ander]]", created="2026-06-27")
        self.assertIn("[[ander]]", md)
        self.assertNotIn("[[a]], [[n]]", md)  # niet per-char gesplitst

    def test_unique_memory_path_avoids_collision(self):
        """Andere inhoud onder dezelfde slug: nummeren, zoals altijd."""
        p1 = _memory.write("Zelfde titel", "een", created="2026-06-27")
        p2, bestaat_al = _memory.unique_memory_path(
            "Zelfde titel", created="2026-06-27", body="iets anders")
        self.assertNotEqual(p1, p2)
        self.assertTrue(p2.name.endswith("-2.md"))
        self.assertFalse(bestaat_al)

    def test_identieke_body_krijgt_geen_tweede_bestand(self):
        """TASK-73: een bezette slug is een SIGNAAL, geen hindernis.

        De functie nummerde blind door zodra het pad bezet was, en produceerde
        zo byte-identieke memories naast elkaar. Nu wordt eerst de body
        vergeleken.
        """
        p1 = _memory.write("Zelfde titel", "exact dezelfde inhoud", created="2026-06-27")
        p2, bestaat_al = _memory.unique_memory_path(
            "Zelfde titel", created="2026-06-27", body="exact dezelfde inhoud")
        self.assertEqual(p1, p2)
        self.assertTrue(bestaat_al)

    def test_body_vergelijking_negeert_omringende_witruimte(self):
        _memory.write("Zelfde titel", "inhoud", created="2026-06-27")
        _p, bestaat_al = _memory.unique_memory_path(
            "Zelfde titel", created="2026-06-27", body="\n  inhoud  \n\n")
        self.assertTrue(bestaat_al)

    def test_zonder_body_wordt_er_gewoon_genummerd(self):
        """Zonder body valt er niets te vergelijken; stil overslaan zou daar
        gevaarlijker zijn dan een duplicaat."""
        p1 = _memory.write("Zelfde titel", "een", created="2026-06-27")
        p2, bestaat_al = _memory.unique_memory_path("Zelfde titel", created="2026-06-27")
        self.assertNotEqual(p1, p2)
        self.assertFalse(bestaat_al)

    def test_derde_identieke_vindt_ook_het_eerste_bestand(self):
        """Met een -2 ernaast die AFWIJKT, moet een identieke body alsnog het
        juiste bestaande bestand vinden in plaats van een -3 te maken."""
        p1 = _memory.write("Zelfde titel", "origineel", created="2026-06-27")
        p2, _ = _memory.unique_memory_path("Zelfde titel", created="2026-06-27",
                                           body="afwijkend")
        p2.write_text(_memory.render("Zelfde titel", "afwijkend", created="2026-06-27"),
                      encoding="utf-8")
        gevonden, bestaat_al = _memory.unique_memory_path(
            "Zelfde titel", created="2026-06-27", body="origineel")
        self.assertTrue(bestaat_al)
        self.assertEqual(gevonden, p1)

    def test_superseded_by_leest_hetzelfde_in_beide_parsers(self):
        """De eigen parser las [[[slug]]] correct, strikte YAML zag een
        drievoudig geneste lijst -- dus in Obsidian stond de eigenschap
        verminkt. Met quotes komen beide op dezelfde waarde uit."""
        from _frontmatter import parse_frontmatter
        p = _memory.write("Oud", "iets", created="2026-06-27")
        _memory.set_status(p, "superseded", superseded_by=["nieuw-artikel"])
        tekst = p.read_text(encoding="utf-8")
        self.assertIn('superseded_by: ["[[nieuw-artikel]]"]', tekst)
        fm, _body = parse_frontmatter(tekst)
        self.assertEqual(fm.get("superseded_by"), ["[[nieuw-artikel]]"])
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML niet aanwezig")
        blok = tekst.split("---")[1]
        self.assertEqual(yaml.safe_load(blok).get("superseded_by"), ["[[nieuw-artikel]]"])


if __name__ == "__main__":
    unittest.main()
