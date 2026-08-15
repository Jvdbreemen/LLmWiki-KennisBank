"""Where a claim came from is known at capture time and was thrown away.

Checking a memory against its own transcript meant RETRIEVING the passage
again, and retrieval finds the right chunk about half the time (TASK-163). The
sweep already has the answer: it is iterating over the chunks when it writes.

The stamp is "N/M" and it validates itself. A reader re-chunks the transcript;
if M does not match what it sees, the chunker changed and every N is off by an
unknown amount, so the only safe answer is "no usable stamp". These tests pin
that refusal, because a confidently wrong passage is worse than none -- the
verifier would judge a claim against text it never came from.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _memory  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


class RenderTest(unittest.TestCase):
    def test_the_stamp_lands_in_the_frontmatter(self):
        fm, _ = parse_frontmatter(
            _memory.render("T", "b", source_session="s.jsonl", source_chunk="3/198"))
        self.assertEqual(fm.get("source_chunk"), "3/198")

    def test_absent_by_default(self):
        """Hand-written and pre-TASK-163 memories have no stamp, and an empty
        key would look like a stamp that failed rather than one never taken."""
        fm, _ = parse_frontmatter(_memory.render("T", "b"))
        self.assertNotIn("source_chunk", fm)


class ChunkFromStampTest(unittest.TestCase):
    CHUNKS = ["first", "second", "third"]

    def test_it_returns_the_chunk_the_claim_came_from(self):
        self.assertEqual(_memory.chunk_from_stamp("2/3", self.CHUNKS), "second")

    def test_one_based_at_both_ends(self):
        self.assertEqual(_memory.chunk_from_stamp("1/3", self.CHUNKS), "first")
        self.assertEqual(_memory.chunk_from_stamp("3/3", self.CHUNKS), "third")

    def test_a_changed_chunker_invalidates_every_index(self):
        """The whole point of carrying M."""
        self.assertIsNone(_memory.chunk_from_stamp("2/3", ["a", "b", "c", "d"]))

    def test_no_stamp_is_not_an_error(self):
        for empty in ("", None):
            self.assertIsNone(_memory.chunk_from_stamp(empty, self.CHUNKS))

    def test_a_malformed_stamp_never_raises(self):
        for junk in ("3", "a/b", "2/3/4", "-1/3", "0/3", "4/3", 7, []):
            with self.subTest(stamp=junk):
                self.assertIsNone(_memory.chunk_from_stamp(junk, self.CHUNKS))

    def test_no_chunks_yields_nothing(self):
        self.assertIsNone(_memory.chunk_from_stamp("1/0", []))


class SweepStampsTheFullCountTest(unittest.TestCase):
    """The denominator must be the transcript's total, not the slice read.

    A normal sweep reads `chunks[:max_chunks]` and a `--all` rebuild reads
    everything. Stamping the slice length would write 3/6 for one and 3/198 for
    the other from the SAME transcript, and a verifier -- which always re-chunks
    the whole thing -- would reject every normally captured memory forever.
    """

    def test_the_stamp_uses_the_full_chunk_count(self):
        src = (SCRIPTS / "memory-sweep.py").read_text(encoding="utf-8")
        stamps = [ln.strip() for ln in src.splitlines() if "source_chunk=" in ln]
        self.assertEqual(len(stamps), 1, f"expected one stamp, got {stamps}")
        # `chunk_iter` is the capped slice and is fine in the progress note,
        # which reports position in what this run reads. In the stamp it would
        # be a lie the verifier cannot detect.
        self.assertNotIn("chunk_iter", stamps[0])
        self.assertIn("len(chunks)", stamps[0])


if __name__ == "__main__":
    unittest.main()
