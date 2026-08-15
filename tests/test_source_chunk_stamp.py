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

import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _memory  # noqa: E402
import _sweeputil as su  # noqa: E402
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

    def test_a_written_memory_points_back_at_the_chunk_it_came_from(self):
        """End to end, against a real multi-chunk transcript.

        The source check below proves the stamp is SPELLED right. It cannot
        prove the value is right, and the two came apart once already: the
        first validation run reported `stamped: 0` because no memory in the
        vault had ever been written with one. This runs the sweep, reads the
        frontmatter it produced, and follows the stamp back to a chunk that has
        to contain the marker the candidate was extracted from.
        """
        tmp = Path(tempfile.mkdtemp(prefix="kb-stamp-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        vault = tmp / "vault"
        (vault / "01-raw" / "transcripts").mkdir(parents=True)
        (vault / "09-memory").mkdir(parents=True)
        (vault / ".claude").mkdir(parents=True)

        saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(vault)
        self.addCleanup(lambda: os.environ.__setitem__("KENNISBANK_VAULT", saved)
                        if saved else os.environ.pop("KENNISBANK_VAULT", None))

        # Long enough to chunk several times, with a marker per paragraph so a
        # candidate can be traced to exactly one chunk.
        paras = [f"MARKER{i:03d} " + ("filler text about the subject at hand. " * 40)
                 for i in range(24)]
        (vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user",
                        "message": {"role": "user", "content": "\n\n".join(paras)}}),
            encoding="utf-8")

        spec = importlib.util.spec_from_file_location(
            "memory_sweep_stamp", str(SCRIPTS / "memory-sweep.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)

        import _embeddings as emb
        import _extract
        import _judge
        import _llm
        originals = (_extract.extract_candidates, _judge.judge, emb.embed,
                     emb.get_cached, _llm.generate)

        def restore():
            (_extract.extract_candidates, _judge.judge, emb.embed,
             emb.get_cached, _llm.generate) = originals
        self.addCleanup(restore)

        def fake_extract(text, max_n=8):
            """The first marker IN the chunk, not its first word.

            Chunks carry 200 characters of the previous one, and that tail is
            filler, so `text.split()[0]` returned the same non-marker word for
            every chunk after the first. Five identical bodies, five dedup
            skips, one memory written -- the fixture failing in a way that
            looked like the sweep failing.
            """
            found = re.search(r"MARKER\d+", text)
            marker = found.group(0) if found else "NONE"
            return [{"title": f"Finding {marker}", "body": f"This is about {marker}."}]

        def fake_embed(text, timeout=30.0, kind=""):
            """One axis per marker, so different candidates are orthogonal.

            Not a detail: the sweep drops a candidate whose cosine against an
            existing memory exceeds 0.92. A cheap fake vector made every
            candidate look like a near-duplicate, one memory got written, and
            this test passed while exercising a single stamp.
            """
            v = [0.0] * 32
            found = re.search(r"MARKER(\d+)", text)
            v[int(found.group(1)) % 32 if found else 31] = 1.0
            return v

        _llm.generate = lambda *a, **k: "ok"
        _extract.extract_candidates = fake_extract
        _judge.judge = lambda cand, context="": {"verdict": "current", "reason": "clear"}
        emb.embed = fake_embed
        emb.get_cached = lambda f, cache, recompute=True: None

        import _sweepstate as ss
        chunks = su.chunk(ss.transcript_text(
            vault / "01-raw" / "transcripts" / "s1.jsonl"))
        self.assertGreater(len(chunks), 1, "transcript must chunk for this to mean anything")

        # The cap MUST bite, or this test cannot see the bug it exists for.
        # `max_chunks` defaults to 40 and this fixture makes about six chunks,
        # so `chunk_iter` would be the whole list and `len(chunk_iter)` would
        # equal `len(chunks)` -- the wrong denominator and the right one would
        # be the same number, and stamping the slice would pass unnoticed.
        cap = len(chunks) - 2
        self.assertGreater(cap, 0)
        m.run_sweep(max_chunks=cap)

        written = sorted((vault / "09-memory").glob("**/*.md"))
        self.assertTrue(written, "the sweep wrote nothing, so nothing was verified")
        stamps = set()
        for f in written:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            with self.subTest(memory=f.stem):
                stamp = fm.get("source_chunk", "")
                self.assertTrue(stamp, "every swept memory carries a stamp")
                self.assertEqual(stamp.split("/")[1], str(len(chunks)),
                                 "the denominator is the whole transcript")
                chunk = _memory.chunk_from_stamp(stamp, chunks)
                self.assertIsNotNone(chunk, f"stamp {stamp} did not resolve")
                marker = body.strip().rsplit(" ", 1)[-1].rstrip(".")
                self.assertIn(marker, chunk,
                              f"{f.stem} points at a chunk without its own marker")
                stamps.add(stamp)
        # One memory with stamp "1/N" would satisfy every assertion above while
        # proving nothing about whether the index tracks the chunk.
        self.assertGreater(len(stamps), 1,
                           f"only one distinct stamp ({stamps}) — the test is vacuous")

    # There was a second test here that read memory-sweep.py and string-matched
    # the `source_chunk=` line for `len(chunks)`. It is gone. It was written
    # because the end-to-end test above could not tell the two denominators
    # apart -- with the cap above the real chunk count, `len(chunk_iter)` and
    # `len(chunks)` are the same number. Now that the cap bites, the behavioural
    # assertion catches the bug directly, and a source-string guard only adds a
    # failure on harmless refactors.


if __name__ == "__main__":
    unittest.main()
