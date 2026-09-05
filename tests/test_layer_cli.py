"""Explicit, opt-in access contracts for the two experimental projections."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LayerCliContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / ".claude").mkdir(parents=True)
        (self.vault / "kennisbank-settings.json").write_text(
            json.dumps({"source_recall": True, "experience_recall": True}),
            encoding="utf-8")
        self.saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.source = load("kb-source-recall.py")
        self.experience = load("kb-experience-recall.py")

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self.saved

    def test_source_requires_an_explicit_non_normal_mode(self):
        result = self.source.run({"prompt": "find source"}, embed_fn=lambda _: [1, 0, 0, 0])
        self.assertEqual(result["status"], "not_routed")

    def test_source_is_fail_open_when_optional_index_is_absent(self):
        result = self.source.run({"mode": "explicit", "prompt": "find source"},
                                 embed_fn=lambda _: [1, 0, 0, 0])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["hits"], [])

    def test_source_hit_contract_labels_route_confidence_and_provenance_state(self):
        hit = {
            "source_path": "01-raw/transcripts/s1.md",
            "source_hash": "sha256:x",
            "chunk_index": 2,
            "start": 10,
            "end": 20,
            "cos": 0.81,
            "fts": True,
            "fresh": True,
            "status": "superseded",
            "conflict": True,
        }
        labeled = self.source.label_hits([hit], "verify")[0]
        self.assertEqual(labeled["retrieval_mode"], "verify")
        self.assertEqual(labeled["confidence"], {
            "cosine": 0.81, "lexical_match": True, "fresh": True,
        })
        self.assertEqual(
            self.source.result_flags([labeled], "verify"),
            ["conflict", "superseded"],
        )

    def test_empty_source_result_is_explicit_no_hit(self):
        self.assertEqual(self.source.result_flags([], "explicit"), ["no_hit"])

    def test_experience_recall_never_returns_candidates(self):
        result = self.experience.run({"mode": "explicit", "prompt": "avoid dead end"},
                                     embed_fn=lambda _: [1, 0, 0, 0])
        self.assertIn(result["status"], {"unavailable", "not_routed"})
        self.assertEqual(result["hits"], [])

    def test_experience_hit_contract_preserves_status_and_labels_advisory(self):
        hit = {
            "experience_id": "failure-1", "status": "validated",
            "outcome_state": "failure", "confidence": 0.8,
            "cos": 0.77, "fts": True, "source_refs": ["raw#1"],
            "outcome_refs": ["out-1"],
        }
        labeled = self.experience.label_hits([hit], "failure")[0]
        self.assertEqual(labeled["status"], "validated")
        self.assertEqual(labeled["recall_mode"], "failure")
        self.assertEqual(labeled["evidence_kind"], "failure_advisory")
        self.assertEqual(labeled["confidence_metadata"], {
            "experience": 0.8, "cosine": 0.77, "lexical_match": True,
            "evidence_bound": True,
        })

    def test_experience_gateway_uses_calibrated_default_but_allows_override(self):
        import _experience as store

        self.assertEqual(self.experience.failure_min_score({}, store), 0.50)
        self.assertEqual(
            self.experience.failure_min_score({"min_score": 0.61}, store), 0.61)

    def test_experience_gateway_executes_real_retrieval_before_labeling(self):
        import _experience as store
        import _source_ref

        db = self.vault / ".claude" / "kb-experience.db"
        source = self.vault / "01-raw" / "transcripts" / "bounded.md"
        source.parent.mkdir(parents=True)
        passage = "use a bounded timeout"
        source.write_text(passage, encoding="utf-8")
        ref = _source_ref.make_source_ref(
            self.vault, "01-raw/transcripts/bounded.md", start=0,
            end=len(passage), chunk_id="bounded-timeout")
        conn = store.connect(db)
        self.addCleanup(conn.close)
        store.ensure_schema(conn)
        store.record_outcome(
            conn, outcome_id="out-1", session_id="s", task_id="t",
            state="success", evidence=[{"kind": "test"}],
            attribution_strength="direct")
        store.save_experience(
            conn, experience_id="bounded-timeout", session_id="s", task_id="t",
            status="candidate", situation="child process can hang",
            approach="bound the timeout", observed_result="shutdown completed",
            lesson="use a bounded timeout", applicability="shutdown helpers",
            outcome_state="success", confidence=0.2,
            source_refs=[ref], outcome_refs=["out-1"])
        stored = store.experience(conn, "bounded-timeout")
        store.record_review(
            conn, review_id="review-bounded-timeout",
            experience_id="bounded-timeout", decision="accepted", actor="test-owner",
            reviewed_at="2026-09-05T10:00:00Z",
            reason="reviewed exact CLI fixture", content_hash=stored["content_hash"])
        store.transition(conn, "bounded-timeout", "validated", vault=self.vault)
        store.ensure_recall_schema(conn, dim=4, embed_id="fake:4")
        store.index_experience(conn, "bounded-timeout", vector=[1, 0, 0, 0])
        result = self.experience.run(
            {"mode": "explicit", "prompt": "bounded timeout", "embed_id": "fake:4"},
            embed_fn=lambda _: [1, 0, 0, 0], vault=self.vault)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hits"][0]["experience_id"], "bounded-timeout")
        self.assertEqual(result["hits"][0]["recall_mode"], "explicit")


if __name__ == "__main__":
    unittest.main()
