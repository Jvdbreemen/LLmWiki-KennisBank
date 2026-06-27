from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import unittest
import _sweeputil as su  # noqa: E402


class SweepUtilTest(unittest.TestCase):
    def test_chunk_splits_long_text(self):
        text = "\n\n".join(f"alinea {i} " + "x" * 500 for i in range(20))
        chunks = su.chunk(text, max_chars=2000)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 2200 for c in chunks))  # max + overlap-marge

    def test_chunk_short_text_one_chunk(self):
        self.assertEqual(su.chunk("kort stukje", max_chars=2000), ["kort stukje"])

    def test_is_duplicate_true_for_near_identical(self):
        v = [1.0, 0.0, 0.0]
        self.assertTrue(su.is_duplicate(v, [[0.99, 0.01, 0.0]], threshold=0.9))

    def test_is_duplicate_false_for_distinct(self):
        self.assertFalse(su.is_duplicate([1.0, 0.0, 0.0], [[0.0, 1.0, 0.0]], threshold=0.9))

    def test_is_duplicate_empty_existing(self):
        self.assertFalse(su.is_duplicate([1.0, 0.0], [], threshold=0.9))


if __name__ == "__main__":
    unittest.main()
