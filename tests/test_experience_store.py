"""Contracts for append-only experience events and evidence-gated projections."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _experience as exp  # noqa: E402
import _source_ref as source_ref_module  # noqa: E402


class ExperienceStoreContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "experience.db"
        self.vault = Path(self.tmp.name) / "vault"
        self.source = self.vault / "01-raw" / "transcripts" / "a.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("bounded subprocess waits", encoding="utf-8")
        self.conn = exp.connect(self.db)
        self.addCleanup(self.conn.close)
        exp.ensure_schema(self.conn)

    def test_events_are_append_only_and_idempotent(self):
        event = dict(event_id="event-1", session_id="s1", task_id="t1",
                     event_type="attempt", observed_at="2026-08-25T10:00:00Z",
                     payload={"approach": "bounded timeout"},
                     source_refs=["01-raw/a.md#0:20"])
        self.assertTrue(exp.append_event(self.conn, **event))
        self.assertFalse(exp.append_event(self.conn, **event))
        changed = dict(event)
        changed["payload"] = {"approach": "unbounded wait"}
        with self.assertRaises(ValueError):
            exp.append_event(self.conn, **changed)

    def test_event_types_are_typed_and_unknown_types_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "event type"):
            exp.append_event(self.conn, event_id="bad", session_id="s1", task_id="t1",
                             event_type="invented", observed_at="now", payload={})

    def test_schema_migration_adds_new_derived_link_columns(self):
        legacy = exp.connect(Path(self.tmp.name) / "legacy.db")
        try:
            legacy.execute(
                "CREATE TABLE experiences (experience_id TEXT PRIMARY KEY, status TEXT, "
                "outcome_state TEXT)")
            legacy.execute(
                "INSERT INTO experiences(experience_id, status, outcome_state) "
                "VALUES ('legacy-failure', 'validated', 'failure')")
            legacy.commit()
            exp.ensure_schema(legacy)
            columns = {row[1] for row in legacy.execute("PRAGMA table_info(experiences)")}
            self.assertTrue({"exposed_refs_json", "procedure_refs_json", "skill_refs_json"}
                            <= columns)
            self.assertTrue({"attempt_state", "resolution_state"} <= columns)
            axes = legacy.execute(
                "SELECT attempt_state, resolution_state FROM experiences "
                "WHERE experience_id='legacy-failure'").fetchone()
            self.assertEqual(axes, ("unknown", "not_applicable"))
        finally:
            legacy.close()

    def test_outcome_preserves_evidence_and_unknown(self):
        exp.record_outcome(self.conn, outcome_id="out-1", session_id="s1",
                           task_id="t1", state="unknown", evidence=[],
                           attribution_strength="none")
        row = exp.outcome(self.conn, "out-1")
        self.assertEqual(row["state"], "unknown")
        self.assertEqual(row["evidence"], [])

    def test_validated_experience_requires_evidence_and_matching_human_review(self):
        common = dict(
            experience_id="exp-1", session_id="s1", task_id="t1",
            situation="child hung", approach="bound timeout",
            observed_result="process stopped", lesson="bound subprocess waits",
            applicability="shutdown helpers", outcome_state="success",
            confidence=0.9)
        with self.assertRaises(ValueError):
            exp.save_experience(self.conn, status="validated", source_refs=[],
                                outcome_refs=[], **common)
        exp.record_outcome(self.conn, outcome_id="out-1", session_id="s1",
                           task_id="t1", state="success",
                           evidence=[{"kind": "test", "value": "passed"}],
                           attribution_strength="none")
        with self.assertRaises(ValueError):
            exp.save_experience(self.conn, status="validated",
                                source_refs=["01-raw/a.md#0:20"],
                                outcome_refs=["out-1"], **common)
        source_ref = source_ref_module.make_source_ref(
            self.vault, "01-raw/transcripts/a.md", start=0,
            end=len("bounded subprocess waits"), chunk_id="chunk-0",
            captured_at="2026-09-04T00:00:00Z")
        exp.save_experience(self.conn, status="candidate",
                            source_refs=[source_ref], outcome_refs=["out-1"], **common)
        content_hash = exp.experience(self.conn, "exp-1")["content_hash"]
        exp.record_review(
            self.conn, review_id="review-1", experience_id="exp-1",
            decision="accepted", actor="owner", reviewed_at="2026-09-04",
            reason="owner verified source and outcome", content_hash=content_hash)
        exp.transition(self.conn, "exp-1", "validated", vault=self.vault)
        self.assertEqual(exp.experience(self.conn, "exp-1")["status"], "validated")

    def test_experience_preserves_exposure_procedure_and_skill_links(self):
        exp.record_outcome(self.conn, outcome_id="out-links", session_id="s1",
                           task_id="t1", state="partial", evidence=[{"kind": "test"}],
                           attribution_strength="weak")
        exp.save_experience(
            self.conn, experience_id="exp-links", session_id="s1", task_id="t1",
            status="candidate", situation="s", approach="a", observed_result="r",
            lesson="l", applicability="scope", outcome_state="partial", confidence=0.4,
            source_refs=["raw#1"], outcome_refs=["out-links"],
            exposed_refs=["memory:m1"], procedure_refs=["procedure:p1"],
            skill_refs=["skill:s1"])
        row = exp.experience(self.conn, "exp-links")
        self.assertEqual(row["exposed_refs"], ["memory:m1"])
        self.assertEqual(row["procedure_refs"], ["procedure:p1"])
        self.assertEqual(row["skill_refs"], ["skill:s1"])

    def test_candidate_may_preserve_uncertainty_but_not_become_validated_implicitly(self):
        exp.save_experience(
            self.conn, experience_id="exp-c", session_id="s1", task_id="t1",
            status="candidate", situation="parser failed", approach="retry",
            observed_result="unknown", lesson="retry may help",
            applicability="unknown", outcome_state="unknown", confidence=0.2,
            source_refs=[], outcome_refs=[])
        self.assertEqual(exp.experience(self.conn, "exp-c")["status"], "candidate")
        with self.assertRaises(ValueError):
            exp.transition(self.conn, "exp-c", "validated")

    def test_supersession_keeps_the_original_record(self):
        for eid in ("old", "new"):
            exp.save_experience(
                self.conn, experience_id=eid, session_id="s", task_id="t",
                status="candidate", situation="s", approach="a",
                observed_result="r", lesson=eid, applicability="scope",
                outcome_state="unknown", confidence=0.4,
                source_refs=[], outcome_refs=[])
        exp.transition(self.conn, "old", "superseded", superseded_by="new")
        old = exp.experience(self.conn, "old")
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_by"], "new")
        self.assertIsNotNone(exp.experience(self.conn, "new"))


if __name__ == "__main__":
    unittest.main()
