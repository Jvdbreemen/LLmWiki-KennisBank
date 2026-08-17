"""Trap 1 of the autonomous review: promote on supported, touch nothing else.

The asymmetry these tests pin is measured, not assumed (TASK-163/195): across
210 checked verdicts `supported` never fabricated its evidence, and in the G0
calibration all 51 of its promotions were confirmed; `unsupported` was never
right when checked (0/20). So promotion may act on one local verdict, and
NOTHING here may ever demote or close.

The promotion edge itself has exactly one legal transition
(unverified -> current); `_memory.promote` refusing every other start status
is the safety property that keeps an autonomous pass from undoing closures
the maintenance machinery made for cause.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _frontmatter import parse_frontmatter  # noqa: E402

# _groundcheck (and through it _embeddings) is imported INSIDE setUp, after
# KENNISBANK_VAULT points at the test's temp vault. _embeddings USED to freeze
# its cache path at import time; on a machine whose profile exports
# KENNISBANK_VAULT a module-level import here froze it onto the REAL vault's
# multi-megabyte embeddings cache -- which every later sweep test then parsed
# on each maintenance pass. Measured: the combined groundcheck+sweep run went
# from 2s to 14 minutes on exactly that. Root-caused since (TASK-196):
# _embeddings.cache_file() resolves per call. The lazy import stays as
# defense-in-depth against the next import-time constant.


def _mods():
    import _groundcheck
    import _memory
    return _groundcheck, _memory


class PromoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-promote-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        global _groundcheck, _memory
        _groundcheck, _memory = _mods()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, stem, status):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text(f"---\ntitle: {stem}\ntype: memory\nstatus: {status}\n"
                     f"created: 2026-08-01\n---\n\nBody van {stem}.\n",
                     encoding="utf-8")
        return p

    def test_promotes_unverified_and_logs_the_evidence(self):
        p = self._write("m1", "unverified")
        ok = _memory.promote(p, reason="passage zegt dit letterlijk",
                             route="stamp", prompt_version=1)
        self.assertTrue(ok)
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        self.assertEqual(fm["status"], "current")
        rows = _memory.recent_promotions()
        self.assertEqual(rows[0]["stem"], "m1")
        self.assertIn("letterlijk", rows[0]["reason"])
        self.assertEqual(rows[0]["prompt_version"], 1)

    def test_every_other_status_is_refused(self):
        """The one legal edge in the status graph, enforced not documented."""
        for status in ("current", "superseded", "retracted", "expired"):
            with self.subTest(status=status):
                p = self._write(f"x-{status}", status)
                before = p.read_text(encoding="utf-8")
                self.assertFalse(_memory.promote(p))
                self.assertEqual(p.read_text(encoding="utf-8"), before,
                                 "refusal must also mean untouched")

    def test_a_missing_file_is_false_not_a_crash(self):
        self.assertFalse(_memory.promote(self.vault / "09-memory" / "nee.md"))


class VerifyPassTest(unittest.TestCase):
    """Drives the real pass against a temp vault with the LLM seam mocked."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-vpass-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)

        global _groundcheck, _memory
        _groundcheck, _memory = _mods()

        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {
                "role": "user", "content": "De drempel is 0.75 geworden."}}),
            encoding="utf-8")

        import _llm
        self._orig_generate = _llm.generate
        self._llm = _llm

    def tearDown(self):
        self._llm.generate = self._orig_generate
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, stem, status="unverified", created="2026-08-01",
             src="s1.jsonl", stamp="1/1"):
        p = self.vault / "09-memory" / f"{stem}.md"
        lines = ["---", f"title: {stem}", "type: memory", f"status: {status}",
                 f'source_session: "{src}"', f"created: {created}"]
        if stamp:
            lines.append(f'source_chunk: "{stamp}"')
        lines += ["---", "", f"Claim uit {stem}.", ""]
        p.write_text("\n".join(lines), encoding="utf-8")
        return p

    def _answer(self, verdict):
        return json.dumps({"verdict": verdict, "reason": "citaat"})

    def test_supported_promotes_and_others_are_left_alone(self):
        a = self._mem("a-supported")
        b = self._mem("b-unsupported")
        c = self._mem("c-notfound")
        answers = {"a-supported": "supported", "b-unsupported": "unsupported",
                   "c-notfound": "not_found"}

        def fake(prompt, system=""):
            for stem, v in answers.items():
                if stem in prompt:
                    return self._answer(v)
            return self._answer("not_found")
        self._llm.generate = fake

        n = _groundcheck.verify_pass()
        self.assertEqual(n, 1)
        self.assertEqual(parse_frontmatter(a.read_text(encoding="utf-8"))[0]["status"],
                         "current")
        for p in (b, c):
            self.assertEqual(parse_frontmatter(p.read_text(encoding="utf-8"))[0]["status"],
                             "unverified", "anything but supported must stay put")

    def test_the_cap_bites_and_oldest_goes_first(self):
        """Capture order drains first, so no memory starves behind newer ones.

        Verified by behaviour: with cap 1 only the OLDEST is promoted."""
        old = self._mem("older", created="2026-07-01")
        new = self._mem("newer", created="2026-08-10")
        self._llm.generate = lambda *a, **k: self._answer("supported")
        n = _groundcheck.verify_pass(max_n=1)
        self.assertEqual(n, 1)
        self.assertEqual(parse_frontmatter(old.read_text(encoding="utf-8"))[0]["status"],
                         "current")
        self.assertEqual(parse_frontmatter(new.read_text(encoding="utf-8"))[0]["status"],
                         "unverified")

    def test_a_dead_model_promotes_nothing(self):
        self._mem("m")
        self._llm.generate = lambda *a, **k: ""
        self.assertEqual(_groundcheck.verify_pass(), 0)

    def test_a_crashing_transcript_reader_skips_not_raises(self):
        self._mem("m", src="s1.jsonl")
        import _sweepstate as ss
        orig = ss.transcript_text
        ss.transcript_text = lambda p: (_ for _ in ()).throw(RuntimeError("kapot"))
        try:
            self.assertEqual(_groundcheck.verify_pass(), 0)
        finally:
            ss.transcript_text = orig

    def test_the_stamp_route_is_used_when_the_stamp_resolves(self):
        self._mem("m", stamp="1/1")
        seen = {}

        def fake(prompt, system=""):
            seen["prompt"] = prompt
            return self._answer("supported")
        self._llm.generate = fake
        _groundcheck.verify_pass()
        # The single-chunk transcript IS the stamped chunk; the passage must
        # be exactly it, not a windowed reconstruction.
        self.assertIn("De drempel is 0.75 geworden.", seen["prompt"])
        rows = _memory.recent_promotions()
        self.assertEqual(rows[0]["route"], "stamp")


class CandidateOrderTest(unittest.TestCase):
    """Trap 1 must remember what it already judged, or it re-judges forever.

    Measured on the real vault (TASK-198): 40 of 40 slots in the cap window
    were memories a client read had already graded `partial`, so the 49
    newer ones were never judged at all. Oldest-first with no record of past
    attempts turns a stable verdict into a permanent occupation of the
    budget.

    The fix ORDERS, it does not exclude: a settled memory returns to the
    queue once the cooldown lapses or the prompt version changes. Trap 1
    reads a selected passage where the client read the whole transcript, so
    it does promote memories the client called `partial` -- disqualifying
    those would kill the only promotions still happening.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cand-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        global _groundcheck, _memory
        _groundcheck, _memory = _mods()
        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {
                "role": "user", "content": "De drempel is 0.75 geworden."}}),
            encoding="utf-8")
        import _llm
        self._orig_generate = _llm.generate
        self._llm = _llm

    def tearDown(self):
        self._llm.generate = self._orig_generate
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, stem, created="2026-08-01"):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text("\n".join([
            "---", f"title: {stem}", "type: memory", "status: unverified",
            'source_session: "s1.jsonl"', f"created: {created}",
            'source_chunk: "1/1"', "---", "", f"Claim uit {stem}.", ""]),
            encoding="utf-8")
        return p

    def _settle(self, stem, days_ago=0, verdict="partial", version=None):
        """Record a decisive trap-1 attempt `days_ago` days in the past."""
        from datetime import datetime, timedelta, timezone
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        _groundcheck.record_attempt(
            self._key(stem), verdict, ts=ts,
            prompt_version=(_groundcheck.VERIFY_PROMPT_VERSION
                            if version is None else version))

    def _key(self, stem):
        return _groundcheck.attempt_key(self.vault / "09-memory" / f"{stem}.md")

    def _stems(self, rows):
        return [Path(r[1]).stem for r in rows]

    def test_never_judged_memories_win_the_cap_over_settled_ones(self):
        """The starvation regression: settled memories may not own the budget.

        Three settled memories are OLDER than two never-judged ones, so plain
        oldest-first would hand them the whole cap of two. It must not.
        """
        for i, day in enumerate(("2026-07-01", "2026-07-02", "2026-07-03")):
            self._mem(f"settled-{i}", created=day)
            self._settle(f"settled-{i}", days_ago=0)
        self._mem("fresh-a", created="2026-08-01")
        self._mem("fresh-b", created="2026-08-02")

        got = self._stems(_groundcheck.candidates(max_n=2))
        self.assertEqual(got, ["fresh-a", "fresh-b"])

    def test_a_settled_memory_returns_once_the_cooldown_lapses(self):
        """Ordering, not exclusion: nothing is disqualified for good."""
        self._mem("old-news", created="2026-07-01")
        self._settle("old-news", days_ago=_groundcheck.VERIFY_RETRY_DAYS + 1)
        self.assertEqual(self._stems(_groundcheck.candidates(max_n=5)),
                         ["old-news"])

    def test_a_recently_settled_memory_is_left_alone(self):
        """With nothing else to do the pass does LESS work, not the same work.

        This is the cost half of the defect: 40 memories re-judged every run
        at 6-8s of local LLM each, for a verdict that never changes.
        """
        self._mem("old-news", created="2026-07-01")
        self._settle("old-news", days_ago=0)
        self.assertEqual(_groundcheck.candidates(max_n=5), [])

    def test_a_prompt_version_bump_reopens_everything(self):
        """A new prompt is the one reason to expect a different answer."""
        self._mem("old-news", created="2026-07-01")
        self._settle("old-news", days_ago=0,
                     version=_groundcheck.VERIFY_PROMPT_VERSION - 1)
        self.assertEqual(self._stems(_groundcheck.candidates(max_n=5)),
                         ["old-news"])

    def test_two_memories_with_one_stem_do_not_share_a_cooldown(self):
        """The scan is recursive and `09-memory/archive/` exists in the wild.

        A bare stem is therefore not a key. Two files may carry the same one,
        and then judging the archived copy would silently buy the live copy a
        week off -- a starvation of exactly the kind this whole change exists
        to remove, one memory at a time and invisible.
        """
        (self.vault / "09-memory" / "archive").mkdir()
        live = self._mem("twin", created="2026-07-01")
        archived = self.vault / "09-memory" / "archive" / "twin.md"
        archived.write_text(live.read_text(encoding="utf-8"), encoding="utf-8")

        _groundcheck.record_attempt(
            _groundcheck.attempt_key(archived), "partial")
        got = [Path(r[1]) for r in _groundcheck.candidates(max_n=5)]
        self.assertIn(live, got, "the live twin was never judged")
        self.assertNotIn(archived, got)

    def test_the_pass_records_the_verdict_that_did_not_promote(self):
        self._mem("m", created="2026-07-01")
        self._llm.generate = lambda *a, **k: json.dumps(
            {"verdict": "partial", "reason": "half"})
        self.assertEqual(_groundcheck.verify_pass(), 0)
        self.assertEqual(
            _groundcheck.load_attempts()[self._key("m")]["verdict"], "partial")

    def test_an_indecisive_answer_is_not_recorded_as_an_attempt(self):
        """A dead or babbling model may not disqualify a memory for a week."""
        self._mem("m", created="2026-07-01")
        self._llm.generate = lambda *a, **k: ""
        self.assertEqual(_groundcheck.verify_pass(), 0)
        self.assertEqual(_groundcheck.load_attempts(), {})


class PromptContractTest(unittest.TestCase):
    def setUp(self):
        global _groundcheck, _memory
        _groundcheck, _memory = _mods()

    def test_the_prompt_is_the_validated_one(self):
        """Byte-level anchors of the prompt 210 checked verdicts validated.
        Change the prompt -> bump the version, or every promote-log line lies
        about its cause."""
        s = _groundcheck.VERIFY_SYSTEM
        self.assertIn("quote the passage", s)
        self.assertIn("not_found", s)
        self.assertIn("do not judge whether the claim is still true today", s)
        self.assertGreaterEqual(_groundcheck.VERIFY_PROMPT_VERSION, 1)

    def test_only_supported_may_promote(self):
        """The asymmetry is the design; grep-proof it in the pass source."""
        src = (SCRIPTS / "_groundcheck.py").read_text(encoding="utf-8")
        self.assertIn('if r["verdict"] != "supported":', src)
        self.assertNotIn("set_status", src.replace("VERIFY_SYSTEM", ""),
                         "trap 1 must have no path to closing a memory")


if __name__ == "__main__":
    unittest.main()
