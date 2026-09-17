"""Contracts for the one-shot reviewed experience holdout evaluator."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "evaluate-experience-holdout.py"
SCRIPTS = SCRIPT.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(1, str(SCRIPTS.parent))

import _experience as experience  # noqa: E402
import _source_ref as source_ref  # noqa: E402


def load_runner():
    spec = importlib.util.spec_from_file_location("experience_holdout_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceHoldoutEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def test_advisory_precision_uses_failure_attempts_and_negative_probes(self):
        cases = [
            {"id": "f1", "expected_experience": "bad-1",
             "expected_attempt_state": "failure"},
            {"id": "f2", "expected_experience": "bad-2",
             "expected_attempt_state": "failure"},
            {"id": "s1", "expected_experience": "good-1",
             "expected_attempt_state": "success"},
            {"id": "n1", "expected_experience": None,
             "expected_attempt_state": "unknown"},
        ]
        warnings = [
            {"id": "f1", "candidate_experience": "bad-1"},
            {"id": "f2", "candidate_experience": "other"},
            {"id": "n1", "candidate_experience": "bad-1"},
        ]

        metrics = self.runner.advisory_metrics(cases, warnings)

        self.assertEqual(metrics["failure_attempts"], 2)
        self.assertEqual(metrics["negative_probes"], 1)
        self.assertEqual(metrics["advisories"], 3)
        self.assertEqual(metrics["correct_advisories"], 1)
        self.assertEqual(metrics["false_warnings"], 1)
        self.assertAlmostEqual(metrics["advisory_precision"], 1 / 3)
        self.assertEqual(metrics["false_warning_rate"], 1.0)

    def test_gate_passes_exact_boundaries_and_requires_hybrid_gain(self):
        retrieval = {
            "failure_hit@3": 0.70,
            "evidence_precision": 1.0,
            "candidate_leakage": 0,
            "retrieval": {"hit@3": 0.80},
        }
        advisories = {"advisory_precision": 0.90, "false_warning_rate": 0.10}

        passed = self.runner.gate_summary(
            retrieval, advisories, lexical_hit3=0.70)
        failed = self.runner.gate_summary(
            retrieval, {**advisories, "advisory_precision": 0.899},
            lexical_hit3=0.70)
        no_gain = self.runner.gate_summary(
            retrieval, advisories, lexical_hit3=0.80)

        self.assertTrue(passed["passes"])
        self.assertFalse(failed["passes"])
        self.assertFalse(no_gain["passes"])
        self.assertFalse(no_gain["checks"]["hybrid_gain"])

    def test_claim_report_atomically_spends_the_holdout_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "holdout-report.json"
            self.runner.require_fresh_report(path)
            self.runner.claim_report(path, input_sha256="sha256:abc")

            marker = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], "running")
            self.assertEqual(marker["input_sha256"], "sha256:abc")
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.runner.claim_report(path, input_sha256="sha256:abc")

    def test_existing_database_blocks_an_accidental_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "holdout.db"
            self.runner.require_fresh_database(path)
            path.write_bytes(b"already attempted")
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.runner.require_fresh_database(path)

    def test_review_contract_rejects_legacy_refs_and_implicit_review(self):
        accepted = {
            "decision": "accepted",
            "actor": "test-human",
            "reviewed_at": "2026-09-05T10:00:00Z",
        }
        with self.assertRaisesRegex(ValueError, "structured source refs"):
            self.runner._review_contract({
                "source_refs": ["01-raw/transcripts/old.md#0:10"],
                "review": accepted,
            })
        with self.assertRaisesRegex(ValueError, "accepted human review"):
            self.runner._review_contract({
                "source_refs": [{"source_ref_id": "sr_test"}],
            })

    def test_synthetic_seed_and_evaluation_smoke(self):
        def record(experience_id, *, attempt_state, outcome_state, token, ref):
            return {
                "experience_id": experience_id,
                "situation": token,
                "goal": "finish safely",
                "approach": token,
                "action": token,
                "observed_result": outcome_state,
                "lesson": token,
                "applicability": "synthetic smoke test",
                "outcome_state": outcome_state,
                "attempt_state": attempt_state,
                "resolution_state": "fix_validated",
                "source_refs": [ref],
                "outcome_refs": [f"out-{experience_id}"],
                "review": {
                    "decision": "accepted",
                    "actor": "test-human",
                    "reviewed_at": "2026-09-05T10:00:00Z",
                    "reason": "reviewed synthetic fixture",
                },
            }

        def vector(text):
            if "rollback" in text:
                return [0.0, 1.0, 0.0, 0.0]
            if "zebra" in text:
                return [0.0, 0.0, 1.0, 0.0]
            return [1.0, 0.0, 0.0, 0.0]

        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            source = vault / "01-raw" / "transcripts" / "holdout.md"
            source.parent.mkdir(parents=True)
            text = "bounded timeout\nrollback failure\n"
            source.write_text(text, encoding="utf-8")

            def ref(passage):
                start = text.index(passage)
                return source_ref.make_source_ref(
                    vault, "01-raw/transcripts/holdout.md", start=start,
                    end=start + len(passage), chunk_id=passage.replace(" ", "-"))

            cases = [
                {
                    "id": "success",
                    "query": "bounded timeout",
                    "expected_experience": "good",
                    "expected_attempt_state": "success",
                    "records": [record(
                        "good", attempt_state="success", outcome_state="success",
                        token="bounded timeout", ref=ref("bounded timeout"))],
                },
                {
                    "id": "failure",
                    "query": "rollback failure",
                    "expected_experience": "bad",
                    "expected_attempt_state": "failure",
                    "records": [record(
                        "bad", attempt_state="failure", outcome_state="success",
                        token="rollback failure", ref=ref("rollback failure"))],
                },
                {
                    "id": "negative",
                    "query": "orthogonal zebra",
                    "expected_experience": None,
                    "expected_attempt_state": "unknown",
                    "records": [],
                },
            ]
            database = vault / "synthetic.db"
            self.runner._seed(
                cases, database, embed_doc=vector, embedding_id="fake:4",
                vault=vault)
            conn = experience.connect(database)
            try:
                stored = experience.experience(conn, "good")
                review = experience.review_for_content(
                    conn, "good", stored["content_hash"])
            finally:
                conn.close()
            self.assertEqual(stored["evidence_state"], "verified")
            self.assertEqual(stored["review_state"], "accepted")
            self.assertEqual(review["actor"], "test-human")
            measured = self.runner._evaluate(
                cases, database, embed_query=vector)

        self.assertEqual(measured["hybrid"]["retrieval"]["hit@3"], 1.0)
        self.assertEqual(measured["hybrid"]["evidence_precision"], 1.0)
        self.assertEqual(measured["advisories"]["correct_advisories"], 1)
        self.assertEqual(measured["advisories"]["false_warnings"], 0)


if __name__ == "__main__":
    unittest.main()
