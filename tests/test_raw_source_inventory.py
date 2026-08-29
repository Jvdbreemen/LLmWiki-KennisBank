"""Privacy-safe raw source inventory contracts."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_raw_sources as audit  # noqa: E402


class RawSourceInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "01-raw/transcripts").mkdir(parents=True)
        (self.vault / "05-bronnen").mkdir(parents=True)
        (self.vault / "08-archive").mkdir(parents=True)
        (self.vault / "01-raw/transcripts/a.md").write_text(
            "---\nsession_id: s1\ncreated: 2026-08-01\n---\nEvidence", encoding="utf-8")
        (self.vault / "05-bronnen/b.txt").write_text("same", encoding="utf-8")
        (self.vault / "08-archive/c.bin").write_bytes(b"ignored")

    def test_inventory_counts_types_metadata_and_duplicate_hashes(self):
        (self.vault / "05-bronnen/copy.txt").write_text("same", encoding="utf-8")
        result = audit.inventory(self.vault)
        self.assertEqual(result["files"], 3)
        self.assertEqual(result["text_files"], 3)
        self.assertEqual(result["binary_files"], 0)
        self.assertEqual(result["missing_metadata"], 2)
        self.assertEqual(result["duplicate_hash_groups"], 1)
        self.assertNotIn("Evidence", json_safe(result))

    def test_redacted_files_are_counted_but_not_content_index_candidates(self):
        path = self.vault / "05-bronnen/private.redacted.txt"
        path.write_text("secret", encoding="utf-8")
        result = audit.inventory(self.vault)
        self.assertEqual(result["redacted_files"], 1)


def json_safe(value):
    return str(value)


if __name__ == "__main__":
    unittest.main()
