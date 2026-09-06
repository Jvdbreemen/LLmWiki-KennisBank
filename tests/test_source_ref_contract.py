"""Production contract for structured, exact source references (TASK-227)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _source_ref_module():
    path = SCRIPTS / "_source_ref.py"
    if not path.is_file():
        raise AssertionError("TASK-228 must provide scripts/_source_ref.py")
    spec = importlib.util.spec_from_file_location("_source_ref_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceRefContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.source = self.vault / "01-raw" / "transcripts" / "sessie.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("vooraf | café en bewijs | achteraf", encoding="utf-8")

    def _ref(self):
        module = _source_ref_module()
        text = self.source.read_text(encoding="utf-8")
        start, end = text.index("café"), text.index(" | achteraf")
        return module, module.make_source_ref(
            self.vault,
            "01-raw/transcripts/sessie.md",
            start=start,
            end=end,
            chunk_id="chunk-0",
            captured_at="2026-09-04T00:00:00Z",
        )

    def test_round_trip_has_complete_deterministic_v1_identity(self):
        module, first = self._ref()
        _, second = self._ref()
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(first["offset_unit"], "unicode_codepoint")
        self.assertEqual(first["source_path"], "01-raw/transcripts/sessie.md")
        for key in ("source_ref_id", "source_sha256", "passage_sha256", "chunk_id"):
            self.assertTrue(first[key])
        result = module.resolve_source_ref(self.vault, first)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["passage"], "café en bewijs")
        source_recall = __import__("_source_recall")
        self.assertEqual(
            source_recall.hydrate_source_ref(self.vault, first), result)

    def test_mutated_source_is_stale_and_never_silently_retargeted(self):
        module, ref = self._ref()
        self.source.write_text("vooraf | ander bewijs | achteraf", encoding="utf-8")
        result = module.resolve_source_ref(self.vault, ref)
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("passage", result)

    def test_warm_snapshot_cache_does_not_hide_a_same_length_rewrite(self):
        module, ref = self._ref()
        self.assertEqual(module.resolve_source_ref(self.vault, ref)["status"], "valid")
        original = self.source.read_text(encoding="utf-8")
        replacement = ("X" if original[0] != "X" else "Y") + original[1:]
        self.assertEqual(len(replacement), len(original))
        self.source.write_text(replacement, encoding="utf-8")
        result = module.resolve_source_ref(self.vault, ref)
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("passage", result)

    def test_traversal_absolute_path_and_unknown_schema_are_rejected(self):
        module = _source_ref_module()
        with self.assertRaises(ValueError):
            module.make_source_ref(self.vault, "../outside.md", start=0, end=1)
        with self.assertRaises(ValueError):
            module.make_source_ref(self.vault, str(self.source.resolve()), start=0, end=1)
        _, ref = self._ref()
        ref["schema_version"] = 999
        self.assertEqual(module.resolve_source_ref(self.vault, ref)["status"], "invalid")

    def test_redacted_and_missing_sources_are_not_hydrated(self):
        module, ref = self._ref()
        ref["redaction_state"] = "redacted"
        self.assertEqual(module.resolve_source_ref(self.vault, ref)["status"], "redacted")
        _, ref = self._ref()
        self.source.unlink()
        self.assertEqual(module.resolve_source_ref(self.vault, ref)["status"], "missing")

    def test_unreadable_source_has_an_explicit_state(self):
        module, ref = self._ref()
        self.source.unlink()
        self.source.mkdir()
        self.assertEqual(module.resolve_source_ref(self.vault, ref)["status"], "unreadable")

    def test_legacy_string_becomes_unverified_candidate_not_a_source_ref(self):
        module = _source_ref_module()
        candidate = module.legacy_source_candidate("01-raw/transcripts/sessie.md")
        self.assertEqual(candidate["evidence_state"], "unverified")
        self.assertIsNone(candidate["source_ref"])
        self.assertEqual(
            candidate["legacy_source_path"], "01-raw/transcripts/sessie.md")

    def test_symlink_cannot_escape_an_approved_root(self):
        outside = self.vault.parent / "outside.md"
        outside.write_text("secret outside the vault", encoding="utf-8")
        link = self.source.parent / "escape.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        module = _source_ref_module()
        with self.assertRaises(ValueError):
            module.make_source_ref(
                self.vault, "01-raw/transcripts/escape.md", start=0, end=6)


if __name__ == "__main__":
    unittest.main()
