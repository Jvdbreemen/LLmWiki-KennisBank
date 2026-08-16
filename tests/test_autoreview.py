"""Trap 2/3 applier: an agent proposes, this code disposes.

The rules under test are the design's safety core (TASK-195): promotion may
follow a single client `supported` (measured trustworthy), retraction needs
DOUBLE agreement — the adjudicator's `absent` AND a failed refutation — plus a
per-run cap, and everything else changes nothing. The privacy gate refuses to
run at all while `auto_review_llm` is off, because bundles exist to be read by
a client LLM and that is cloud.

Imports happen inside setUp, after the env points at a temp vault: module-
level imports here would freeze _embeddings.CACHE_FILE onto the real vault
during collection and tax every later test (TASK-196, measured at 835s).
"""
from __future__ import annotations

import importlib.util
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


def _load_autoreview():
    spec = importlib.util.spec_from_file_location(
        "kb_autoreview", str(SCRIPTS / "kb-autoreview.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class AutoReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-areview-"))
        self.vault = self.tmp / "vault"
        (self.vault / "01-raw" / "transcripts").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        (self.vault / "01-raw" / "transcripts" / "s1.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user",
                                                    "content": "inhoud"}}),
            encoding="utf-8")
        self.mod = _load_autoreview()
        import _settings
        self._settings = _settings
        _settings.set("auto_review_llm", True)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, stem, status="unverified"):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text(f"---\ntitle: {stem}\ntype: memory\nstatus: {status}\n"
                     f'source_session: "s1.jsonl"\ncreated: 2026-08-01\n---\n\n'
                     f"Claim {stem}.\n", encoding="utf-8")
        return p

    def _status(self, p):
        return parse_frontmatter(p.read_text(encoding="utf-8"))[0]["status"]

    def _apply(self, rows, **kw):
        rp = self.tmp / "results.json"
        rp.write_text(json.dumps(rows), encoding="utf-8")
        rc = self.mod.apply(str(rp), **kw)
        self.assertEqual(rc, 0)
        return rp

    # -- the privacy gate ---------------------------------------------------

    def test_the_toggle_gates_both_subcommands(self):
        """Off means refused, loudly, before any bundle or status change."""
        self._settings.set("auto_review_llm", False)
        m = self._mem("m")
        self.assertEqual(self.mod.bundle(), 1)
        self.assertEqual((self.vault / ".claude" / "autoreview").exists(), False)
        rp = self.tmp / "r.json"
        rp.write_text(json.dumps([{"stem": "m", "verdict": "supported",
                                   "evidence": "x", "refuted": None}]),
                      encoding="utf-8")
        self.assertEqual(self.mod.apply(str(rp)), 1)
        self.assertEqual(self._status(m), "unverified")

    # -- apply rules ----------------------------------------------------------

    def test_supported_promotes_with_the_evidence(self):
        m = self._mem("m")
        self._apply([{"stem": "m", "verdict": "supported",
                      "evidence": "citaat uit transcript", "refuted": None}])
        self.assertEqual(self._status(m), "current")
        import _memory
        self.assertIn("citaat", _memory.recent_promotions()[0]["reason"])
        self.assertEqual(_memory.recent_promotions()[0]["route"], "client")

    def test_retraction_requires_double_agreement(self):
        """absent alone, or absent with an overturned refutation, changes
        nothing; only absent + refuted:false retracts."""
        alone = self._mem("alone")
        overturned = self._mem("overturned")
        agreed = self._mem("agreed")
        self._apply([
            {"stem": "alone", "verdict": "absent", "evidence": "", "refuted": None},
            {"stem": "overturned", "verdict": "absent", "evidence": "", "refuted": True},
            {"stem": "agreed", "verdict": "absent", "evidence": "", "refuted": False},
        ])
        self.assertEqual(self._status(alone), "unverified")
        self.assertEqual(self._status(overturned), "unverified")
        self.assertEqual(self._status(agreed), "retracted")

    def test_the_retract_cap_bites(self):
        mems = [self._mem(f"m{i}") for i in range(4)]
        self._apply([{"stem": f"m{i}", "verdict": "absent", "evidence": "",
                      "refuted": False} for i in range(4)], retract_cap=2)
        statuses = sorted(self._status(p) for p in mems)
        self.assertEqual(statuses.count("retracted"), 2)
        self.assertEqual(statuses.count("unverified"), 2)

    def test_partial_and_unclear_change_nothing(self):
        a = self._mem("a")
        b = self._mem("b")
        self._apply([{"stem": "a", "verdict": "partial", "evidence": "x", "refuted": None},
                     {"stem": "b", "verdict": "unclear", "evidence": "", "refuted": None}])
        self.assertEqual(self._status(a), "unverified")
        self.assertEqual(self._status(b), "unverified")

    def test_a_result_for_a_non_unverified_memory_is_ignored(self):
        """A stale results file may not touch what changed state meanwhile."""
        m = self._mem("m", status="current")
        self._apply([{"stem": "m", "verdict": "absent", "evidence": "",
                      "refuted": False}])
        self.assertEqual(self._status(m), "current")

    def test_an_invalid_verdict_is_ignored(self):
        m = self._mem("m")
        self._apply([{"stem": "m", "verdict": "retract-now", "evidence": "",
                      "refuted": False}])
        self.assertEqual(self._status(m), "unverified")

    # -- bundle ---------------------------------------------------------------

    def test_bundle_writes_cases_and_manifest(self):
        self._mem("m1")
        self._mem("m2")
        self.assertEqual(self.mod.bundle(), 0)
        batches = list((self.vault / ".claude" / "autoreview").iterdir())
        self.assertEqual(len(batches), 1)
        manifest = json.loads((batches[0] / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 2)
        case = batches[0] / manifest[0]["case"]
        self.assertTrue((case / "claim.md").exists())
        self.assertTrue((case / "transcript.txt").exists())


if __name__ == "__main__":
    unittest.main()
