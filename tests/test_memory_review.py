"""Tests voor de menselijke review-laag in _memory (TASK-89, Spoor D1).

De harde eisen: gesloten actieset met expliciete skip, alleen unverified
beslisbaar, traversal-guard, en de crash-veilige volgorde — een fout mag
NOOIT als beslissing verschijnen (llm_wiki #614-les).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from tests._loader import load_script  # noqa: E402


def _memory_md(title, status="unverified", created="2026-07-01",
               memory_type="feit", evidence="cc-sessie"):
    return (f"---\ntitle: '{title}'\ntype: memory\nmemory_type: {memory_type}\n"
            f"importance: 3\nstatus: {status}\nevidence_basis: {evidence}\n"
            f"source_session: ''\ncreated: {created}\nupdated: {created}\n"
            f"valid_from: {created}\ntags: []\n---\n\nKerninhoud van {title}.\n")


class ReviewTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        import importlib
        import _memory
        importlib.reload(_memory)
        self.mem = _memory

    def _write(self, stem, **kw):
        p = self.vault / "09-memory" / f"{stem}.md"
        p.write_text(_memory_md(stem, **kw), encoding="utf-8")
        return p


class DecideTest(ReviewTestBase):
    def test_approve_promotes_to_current_and_logs(self):
        p = self._write("u1")
        r = self.mem.decide("u1", "approve", via="test")
        self.assertEqual(r, {"status": "ok", "stem": "u1", "new_status": "current"})
        self.assertEqual(self.mem.read_status(p), "current")
        log = self.mem.review_log_path().read_text(encoding="utf-8")
        entry = json.loads(log.strip().splitlines()[-1])
        self.assertEqual((entry["stem"], entry["decision"], entry["via"]),
                         ("u1", "approve", "test"))

    def test_reject_retracts(self):
        p = self._write("u2")
        r = self.mem.decide("u2", "reject")
        self.assertEqual(r["new_status"], "retracted")
        self.assertEqual(self.mem.read_status(p), "retracted")

    def test_skip_writes_nothing_but_logs(self):
        p = self._write("u3")
        before = p.read_text(encoding="utf-8")
        r = self.mem.decide("u3", "skip")
        self.assertEqual(r["status"], "skipped")
        self.assertEqual(p.read_text(encoding="utf-8"), before)
        self.assertIn('"skip"', self.mem.review_log_path().read_text(encoding="utf-8"))

    def test_invalid_decision_is_400(self):
        self._write("u4")
        with self.assertRaises(self.mem.ReviewError) as ctx:
            self.mem.decide("u4", "promote")
        self.assertEqual(ctx.exception.code, 400)

    def test_traversal_guard(self):
        for bad in ("../u5", "a/../b", "a\\b", ""):
            with self.assertRaises(self.mem.ReviewError) as ctx:
                self.mem.decide(bad, "approve")
            self.assertEqual(ctx.exception.code, 400)

    def test_missing_is_404(self):
        with self.assertRaises(self.mem.ReviewError) as ctx:
            self.mem.decide("bestaat-niet", "approve")
        self.assertEqual(ctx.exception.code, 404)

    def test_non_unverified_is_409(self):
        self._write("c1", status="current")
        with self.assertRaises(self.mem.ReviewError) as ctx:
            self.mem.decide("c1", "reject")
        self.assertEqual(ctx.exception.code, 409)

    def test_failed_write_never_reports_success(self):
        """Crash-veiligheid (llm_wiki #614): set_status faalt -> ReviewError,
        bestand onveranderd, GEEN audit-regel, item blijft beslisbaar."""
        p = self._write("u6")
        before = p.read_text(encoding="utf-8")
        with patch.object(self.mem, "set_status", return_value=False):
            with self.assertRaises(self.mem.ReviewError) as ctx:
                self.mem.decide("u6", "approve")
        self.assertEqual(ctx.exception.code, 500)
        self.assertEqual(p.read_text(encoding="utf-8"), before)
        self.assertFalse(self.mem.review_log_path().exists(),
                         "audit-regel geschreven terwijl de beslissing faalde")
        # en daarna gewoon opnieuw beslisbaar:
        r = self.mem.decide("u6", "approve")
        self.assertEqual(r["new_status"], "current")

    def test_audit_failure_does_not_undo_decision(self):
        """De audit is fail-soft: een kapotte log-schrijfweg (hier: het pad
        zelf gooit) mag een al duurzaam genomen besluit niet breken."""
        p = self._write("u7")
        with patch.object(self.mem, "review_log_path",
                          side_effect=OSError("schijf vol")):
            r = self.mem.decide("u7", "approve")
        self.assertEqual(r["new_status"], "current")
        self.assertEqual(self.mem.read_status(p), "current")


class PendingReviewsTest(ReviewTestBase):
    def test_only_unverified_oldest_first(self):
        self._write("b-nieuw", created="2026-07-20")
        self._write("a-oud", created="2026-07-01")
        self._write("klaar", status="current")
        items = self.mem.pending_reviews()
        self.assertEqual([i["stem"] for i in items], ["a-oud", "b-nieuw"])
        self.assertTrue(all("snippet" in i and "age_days" in i for i in items))

    def test_limit(self):
        for i in range(5):
            self._write(f"u{i}", created=f"2026-07-0{i + 1}")
        self.assertEqual(len(self.mem.pending_reviews(limit=2)), 2)

    def test_empty_dir_is_empty(self):
        self.assertEqual(self.mem.pending_reviews(), [])


class ReviewCountsTest(ReviewTestBase):
    def test_counts_by_decision(self):
        for stem, d in (("u1", "approve"), ("u2", "approve"), ("u3", "reject"),
                        ("u4", "skip")):
            self._write(stem)
            self.mem.decide(stem, d)
        c = self.mem.review_counts(30)
        self.assertEqual((c["approve"], c["reject"], c["skip"]), (2, 1, 1))

    def test_missing_log_is_zero(self):
        c = self.mem.review_counts(30)
        self.assertEqual(sum(c.values()), 0)


class Task23ReplayTest(ReviewTestBase):
    """Bewijs-scenario (TASK-89 AC#5/#9): de TASK-23-stuwing — 31 unverified
    memories na een Ollama-outage — is via de reguliere review-flow leeg te
    werken, zonder one-off script."""

    def test_31_backed_up_memories_cleared_via_review_flow(self):
        for i in range(31):
            self._write(f"outage-{i:02d}", created="2026-06-15")
        self.assertEqual(len(self.mem.pending_reviews()), 31)
        # de mens beslist per item (hier gesimuleerd: 25 approve, 6 reject —
        # de verhouding uit TASK-23, waar 25/31 correct bleek)
        for i, it in enumerate(self.mem.pending_reviews()):
            self.mem.decide(it["stem"], "approve" if i < 25 else "reject",
                            via="command")
        self.assertEqual(self.mem.pending_reviews(), [])
        c = self.mem.review_counts(30)
        self.assertEqual((c["approve"], c["reject"]), (25, 6))
        statuses = [self.mem.read_status(p)
                    for p in sorted((self.vault / "09-memory").glob("*.md"))]
        self.assertEqual(statuses.count("current"), 25)
        self.assertEqual(statuses.count("retracted"), 6)


class MemoryDoctorCliTest(ReviewTestBase):
    def _doctor(self):
        return load_script("memory-doctor.py")

    def test_pending_json_and_decide_roundtrip(self):
        self._write("u1")
        doc = self._doctor()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doc.main(["pending", "--json"])
        self.assertEqual(rc, 0)
        items = json.loads(buf.getvalue())
        self.assertEqual(items[0]["stem"], "u1")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = doc.main(["decide", "u1", "approve"])
        self.assertEqual(rc, 0)
        self.assertIn("current", buf.getvalue())

    def test_decide_error_exits_nonzero(self):
        doc = self._doctor()
        rc = doc.main(["decide", "bestaat-niet", "approve"])
        self.assertEqual(rc, 1)

    def test_decide_usage_error(self):
        doc = self._doctor()
        self.assertEqual(doc.main(["decide", "alleen-stem"]), 2)


if __name__ == "__main__":
    unittest.main()
