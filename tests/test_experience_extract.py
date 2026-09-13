"""Deterministic, evidence-bound experience extraction contracts."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _experience as exp  # noqa: E402
import _experience_extract as extract  # noqa: E402


class ExperienceExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = exp.connect(Path(self.tmp.name) / "experience.db")
        self.addCleanup(self.conn.close)
        exp.ensure_schema(self.conn)

    def test_successful_evidence_becomes_unreviewed_candidate(self):
        exp.append_event(self.conn, event_id="e1", session_id="s", task_id="t",
                         event_type="attempt", observed_at="now",
                         payload={"situation": "child hung", "approach": "bound timeout",
                                  "lesson": "use bounded timeout", "applicability": "shutdown"},
                         source_refs=["raw.md#1:4"])
        exp.record_outcome(self.conn, outcome_id="o1", session_id="s", task_id="t",
                           state="success", evidence=[{"kind": "test"}],
                           attribution_strength="none")
        result = extract.derive_experience(self.conn, "s", "t", "x1")
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["evidence_state"], "unverified")
        self.assertEqual(result["review_state"], "unreviewed")
        self.assertEqual(exp.experience(self.conn, "x1")["outcome_state"], "success")

    def test_unknown_or_missing_evidence_stays_candidate(self):
        exp.append_event(self.conn, event_id="e2", session_id="s", task_id="t",
                         event_type="observation", observed_at="now",
                         payload={"lesson": "retry may help"}, source_refs=[])
        result = extract.derive_experience(self.conn, "s", "t", "x2")
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["outcome_state"], "unknown")

    def test_failure_is_retained_and_rebuild_is_idempotent(self):
        exp.append_event(self.conn, event_id="e3", session_id="s", task_id="t",
                         event_type="failure", observed_at="now",
                         payload={"situation": "scene failed", "approach": "scene prior",
                                  "observed_result": "regression", "lesson": "avoid scene prior"},
                         source_refs=["raw.md#5:8"])
        exp.record_outcome(self.conn, outcome_id="o3", session_id="s", task_id="t",
                           state="failure", evidence=[{"kind": "revert"}],
                           attribution_strength="none")
        first = extract.derive_experience(self.conn, "s", "t", "x3")
        second = extract.derive_experience(self.conn, "s", "t", "x3")
        self.assertEqual(first["status"], "candidate")
        self.assertEqual(second["created"], False)
        self.assertEqual(second["outcome_state"], "failure")

    def test_conflicting_outcomes_remain_candidate(self):
        exp.append_event(self.conn, event_id="e-conflict", session_id="s", task_id="t",
                         event_type="observation", observed_at="now",
                         payload={"situation": "ambiguous", "approach": "try"},
                         source_refs=["raw.md#1:2"])
        exp.record_outcome(self.conn, outcome_id="o-success", session_id="s", task_id="t",
                           state="success", evidence=[{"kind": "test", "value": "passed"}],
                           attribution_strength="none")
        exp.record_outcome(self.conn, outcome_id="o-failure", session_id="s", task_id="t",
                           state="failure", evidence=[{"kind": "test", "value": "failed"}],
                           attribution_strength="none")
        result = extract.derive_experience(self.conn, "s", "t", "conflicting")
        self.assertEqual(result["outcome_state"], "mixed")
        self.assertEqual(result["status"], "candidate")

    def test_attempt_resolution_and_attribution_are_preserved_separately(self):
        exp.append_event(
            self.conn, event_id="typed", session_id="s", task_id="t",
            event_type="fix", observed_at="now",
            payload={"lesson": "bound retries", "attempt_state": "failure",
                     "resolution_state": "fix_validated",
                     "attribution_limits": "single task observation"},
            source_refs=["raw.md#1:2"])
        exp.record_outcome(
            self.conn, outcome_id="typed-outcome", session_id="s", task_id="t",
            state="success", evidence=["tests passed"],
            attribution_strength="correlated")

        result = extract.derive_experience_values(self.conn, "s", "t", "typed-exp")

        self.assertEqual(result["attempt_state"], "failure")
        self.assertEqual(result["resolution_state"], "fix_validated")
        self.assertEqual(result["outcome_state"], "success")
        self.assertEqual(result["attribution_limits"], "single task observation")

    def test_dead_end_survival_report_counts_failure_events_retained_as_lessons(self):
        events = [
            {"event_type": "failure", "source_refs": ["raw#1"],
             "payload": {"lesson": "avoid retry storm"}},
            {"event_type": "failure", "source_refs": ["raw#2"],
             "payload": {"observed_result": "regression"}},
        ]
        records = [{"source_refs": ["raw#1"], "lesson": "avoid retry storm"}]
        report = extract.dead_end_survival_report(events, records)
        self.assertEqual(report["dead_end_events"], 2)
        self.assertEqual(report["survived_events"], 1)
        self.assertEqual(report["survival_rate"], 0.5)
        self.assertEqual(report["decision"], "review")

    def test_consolidation_is_bounded_idempotent_and_does_not_mutate_episodes(self):
        records = [
            {"experience_id": "failure-1", "status": "validated",
             "outcome_state": "failure", "lesson": "avoid scene prior",
             "applicability": "memory ranking", "source_refs": ["raw#1"],
             "outcome_refs": ["out-1"]},
            {"experience_id": "failure-2", "status": "validated",
             "outcome_state": "failure", "lesson": "avoid scene prior",
             "applicability": "memory ranking", "source_refs": ["raw#2"],
             "outcome_refs": ["out-2"]},
        ]
        before = repr(records)
        first = extract.consolidation_report(records, min_support=2)
        second = extract.consolidation_report(records, min_support=2)
        self.assertEqual(first, second)
        self.assertEqual(len(first["proposals"]), 1)
        proposal = first["proposals"][0]
        self.assertEqual(proposal["support"], 2)
        self.assertEqual(proposal["outcome_state"], "failure")
        self.assertTrue(proposal["reversible"])
        self.assertFalse(first["mutated"])
        self.assertEqual(repr(records), before)

    def test_malformed_derived_payload_fails_open_and_keeps_raw_event(self):
        self.conn.execute(
            "INSERT INTO experience_events(event_id, session_id, task_id, event_type, "
            "observed_at, payload_json, source_refs_json, schema_version) "
            "VALUES ('bad', 's', 't', 'observation', 'now', '{broken', '[]', '1')")
        self.conn.commit()
        result = extract.derive_experience(self.conn, "s", "t", "malformed")
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM experience_events WHERE event_id='bad'"
        ).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
