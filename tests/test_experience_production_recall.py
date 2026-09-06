"""Production contracts for explicit, reviewed experience recall."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _experience as experience  # noqa: E402


def _gateway():
    spec = importlib.util.spec_from_file_location(
        "experience_production_gateway", SCRIPTS / "kb-experience-recall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceProductionRecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        self.db = experience.projection_path(self.vault)
        self.db.parent.mkdir(parents=True)
        self.conn = experience.connect(self.db)
        self.addCleanup(self.conn.close)
        experience.ensure_projection_schema(self.conn, dim=3, embed_id="fake:3")

    @staticmethod
    def _ref(name: str) -> dict:
        return {
            "schema_version": 1,
            "source_ref_id": f"sr_{name}",
            "source_path": f"01-raw/transcripts/{name}.md",
            "source_sha256": "sha256:" + "a" * 64,
            "chunk_id": "chunk-0",
            "start": 0,
            "end": 12,
            "offset_unit": "unicode_codepoint",
            "passage_sha256": "sha256:" + "b" * 64,
            "captured_at": "2026-09-06T00:00:00Z",
            "redaction_state": "clear",
        }

    def _record(self, eid: str, *, task: str, lesson: str, source: str,
                status: str = "validated", evidence: str = "verified",
                review: str = "accepted") -> dict:
        return {
            "experience_id": eid, "session_id": "session", "task_id": task,
            "status": status, "situation": lesson, "goal": "finish safely",
            "approach": lesson, "action": f"apply {lesson}",
            "observed_result": "verified result", "lesson": lesson,
            "applicability": "repository maintenance",
            "outcome_state": "success", "attempt_state": "failure",
            "resolution_state": "fix_validated", "confidence": 0.8,
            "source_refs": [self._ref(source)], "outcome_refs": [f"out-{eid}"],
            "evidence_state": evidence, "review_state": review,
            "content_hash": "sha256:" + eid.encode().hex().ljust(64, "0")[:64],
        }

    def _index(self, record: dict, vector) -> None:
        experience.projection_upsert(self.conn, record)
        experience.index_experience(self.conn, record["experience_id"], vector=vector)

    def test_default_search_excludes_unverified_or_unaccepted_rows(self):
        self._index(self._record(
            "safe", task="t1", lesson="bounded timeout", source="safe"),
            [1, 0, 0])
        self._index(self._record(
            "unverified", task="t2", lesson="bounded timeout guess", source="guess",
            evidence="unverified"), [1, 0, 0])
        self._index(self._record(
            "unreviewed", task="t3", lesson="bounded timeout draft", source="draft",
            review="unreviewed"), [1, 0, 0])

        hits = experience.experience_hits(
            self.conn, query_vector=[1, 0, 0], query_text="bounded timeout", k=20)

        self.assertEqual([hit["experience_id"] for hit in hits], ["safe"])

    def test_legacy_string_source_reference_is_not_publicly_searchable(self):
        record = self._record(
            "legacy", task="t1", lesson="bounded timeout", source="legacy")
        record["source_refs"] = ["01-raw/transcripts/legacy.md#0:12"]
        self._index(record, [1, 0, 0])

        hits = experience.experience_hits(
            self.conn, query_vector=[1, 0, 0], query_text="bounded timeout")

        self.assertEqual(hits, [])

    def test_results_are_capped_and_diversified_by_task_and_source(self):
        fixtures = (
            ("a", "same-task", "bounded timeout primary", "same", [1, 0, 0]),
            ("duplicate", "same-task", "bounded timeout duplicate", "same", [0.99, 0.01, 0]),
            ("b", "task-b", "bounded timeout cleanup", "b", [0.98, 0.02, 0]),
            ("c", "task-c", "bounded timeout shutdown", "c", [0.97, 0.03, 0]),
            ("d", "task-d", "bounded timeout rollback", "d", [0.96, 0.04, 0]),
        )
        for eid, task, lesson, source, vector in fixtures:
            self._index(self._record(
                eid, task=task, lesson=lesson, source=source), vector)

        hits = experience.experience_hits(
            self.conn, query_vector=[1, 0, 0], query_text="bounded timeout", k=20)

        self.assertEqual(len(hits), 3)
        self.assertEqual(len({hit["task_id"] for hit in hits}), 3)
        source_sets = [set(hit["source_ref_ids"]) for hit in hits]
        self.assertTrue(all(not left & right for index, left in enumerate(source_sets)
                            for right in source_sets[index + 1:]))

    def test_failure_mode_is_disabled_before_settings_or_embedding(self):
        gateway = _gateway()
        settings = importlib.import_module("_settings")
        with mock.patch.object(settings, "get", side_effect=AssertionError("settings touched")):
            result = gateway.run(
                {"mode": "failure", "prompt": "warn me"},
                embed_fn=lambda _text: (_ for _ in ()).throw(
                    AssertionError("embedding touched")), vault=self.vault)
        self.assertEqual(result, {"status": "policy_disabled", "hits": [],
                                  "mode": "failure"})

    def test_embedding_failure_returns_labelled_lexical_fallback(self):
        self._index(self._record(
            "safe", task="t1", lesson="bounded timeout", source="safe"),
            [1, 0, 0])
        gateway = _gateway()
        settings = importlib.import_module("_settings")
        with mock.patch.object(settings, "get", return_value=True):
            result = gateway.run(
                {"mode": "explicit", "prompt": "bounded timeout"},
                embed_fn=lambda _text: (_ for _ in ()).throw(RuntimeError("offline")),
                vault=self.vault)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retrieval_route"], "lexical_fallback")
        self.assertEqual(result["hits"][0]["retrieval_route"], "lexical_fallback")

    def test_incompatible_vector_metadata_falls_back_without_mutation(self):
        self._index(self._record(
            "safe", task="t1", lesson="bounded timeout", source="safe"),
            [1, 0, 0])
        before = self.conn.execute(
            "SELECT value FROM meta WHERE key='embed_id'").fetchone()[0]
        gateway = _gateway()
        settings = importlib.import_module("_settings")
        with mock.patch.object(settings, "get", return_value=True):
            result = gateway.run(
                {"mode": "explicit", "prompt": "bounded timeout",
                 "embed_id": "other:3"}, embed_fn=lambda _text: [1, 0, 0],
                vault=self.vault)
        after = self.conn.execute(
            "SELECT value FROM meta WHERE key='embed_id'").fetchone()[0]

        self.assertEqual(result["retrieval_route"], "lexical_fallback")
        self.assertEqual((before, after), ("fake:3", "fake:3"))

    def test_public_hit_contains_lesson_states_scores_and_ids_but_no_raw_ref(self):
        self._index(self._record(
            "safe", task="t1", lesson="bounded timeout", source="safe"),
            [1, 0, 0])
        gateway = _gateway()
        settings = importlib.import_module("_settings")
        with mock.patch.object(settings, "get", return_value=True):
            result = gateway.run(
                {"mode": "explicit", "prompt": "bounded timeout",
                 "embed_id": "fake:3", "k": 99},
                embed_fn=lambda _text: [1, 0, 0], vault=self.vault)
        hit = result["hits"][0]

        self.assertEqual(result["retrieval_route"], "hybrid")
        self.assertEqual(hit["source_ref_ids"], ["sr_safe"])
        for key in ("lesson", "applicability", "attempt_state",
                    "resolution_state", "outcome_state", "validation_stamp",
                    "score", "retrieval_route"):
            self.assertIn(key, hit)
        self.assertNotIn("source_refs", hit)
        self.assertNotIn("passage", repr(result).lower())

    def test_warm_explicit_recall_p95_is_below_budget(self):
        self._index(self._record(
            "safe", task="t1", lesson="bounded timeout", source="safe"),
            [1, 0, 0])
        gateway = _gateway()
        settings = importlib.import_module("_settings")
        latencies = []
        with mock.patch.object(settings, "get", return_value=True):
            for _ in range(31):
                started = time.perf_counter()
                result = gateway.run(
                    {"mode": "explicit", "prompt": "bounded timeout",
                     "embed_id": "fake:3"}, embed_fn=lambda _text: [1, 0, 0],
                    vault=self.vault)
                latencies.append((time.perf_counter() - started) * 1000.0)
        self.assertEqual(result["status"], "ok")
        ordered = sorted(latencies[1:])
        p95 = ordered[int(0.95 * (len(ordered) - 1))]
        self.assertLessEqual(p95, 250.0)


if __name__ == "__main__":
    unittest.main()
