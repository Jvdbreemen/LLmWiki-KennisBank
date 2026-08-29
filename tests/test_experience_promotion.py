"""Proposal-only promotion contracts for validated experiences."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _experience_promote as promote  # noqa: E402


def record(eid, lesson, state="success", status="validated", scope="repo"):
    return {"experience_id": eid, "lesson": lesson, "outcome_state": state,
            "status": status, "applicability": scope,
            "action": "apply bounded timeout",
            "source_refs": [eid + "-source"], "outcome_refs": [eid + "-outcome"]}


class ExperiencePromotionTest(unittest.TestCase):
    def test_repeated_validated_evidence_creates_a_proposal(self):
        report = promote.proposal_report([
            record("a", "bound timeout"), record("b", "bound timeout")])
        self.assertEqual(len(report["proposals"]), 1)
        self.assertEqual(report["proposals"][0]["support"], 2)
        self.assertTrue(report["human_approval_required"])

    def test_candidate_or_conflicting_records_are_rejected(self):
        report = promote.proposal_report([
            record("a", "retry", status="candidate"),
            record("b", "retry", state="failure")])
        self.assertEqual(report["proposals"], [])
        self.assertTrue(report["rejections"])

    def test_single_success_is_not_enough(self):
        report = promote.proposal_report([record("a", "one-off")])
        self.assertEqual(report["proposals"], [])

    def test_proposal_requires_concrete_steps_and_reports_outcome_quality(self):
        records = [record("a", "bound timeout"), record("b", "bound timeout")]
        report = promote.proposal_report(records)
        proposal = report["proposals"][0]
        self.assertEqual(proposal["actions"], ["apply bounded timeout"])
        self.assertEqual(proposal["outcome_quality"], "success")

    def test_stale_or_retracted_experiences_are_rejected_without_override(self):
        stale = record("old", "old lesson")
        stale["valid_until"] = "2026-01-01"
        retracted = record("gone", "old lesson", status="retracted")
        report = promote.proposal_report(
            [stale, retracted], as_of="2026-08-26")
        self.assertEqual(report["proposals"], [])
        self.assertTrue(all("rejected" in item["reason"] or "valid" in item["reason"]
                            for item in report["rejections"]))

    def test_conflicting_outcomes_are_rejected_even_with_repeated_support(self):
        report = promote.proposal_report([
            record("a", "lesson", state="success"),
            record("b", "lesson", state="failure"),
        ])
        self.assertEqual(report["proposals"], [])
        self.assertIn("conflicting", report["rejections"][0]["reason"])

    def test_owner_rejection_is_explicit_and_does_not_mutate(self):
        report = promote.proposal_report([record("a", "lesson"), record("b", "lesson")])
        proposal = report["proposals"][0]
        decision = promote.review_proposal(report, proposal["proposal_id"], "reject")
        self.assertEqual(decision["decision"], "reject")
        self.assertFalse(decision["approved"])
        self.assertFalse(decision["mutated"])


if __name__ == "__main__":
    unittest.main()
