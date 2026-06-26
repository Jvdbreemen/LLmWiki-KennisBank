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
        self.assertIn("cc-sessie", _memory.EVIDENCE_BASES)

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


if __name__ == "__main__":
    unittest.main()
