"""Contracts for the private interactive paired-action review workflow."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "experience-action-review.py"


def load_script():
    spec = importlib.util.spec_from_file_location("experience_action_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExperienceActionReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_script()

    def test_prompts_share_task_and_normal_context(self):
        baseline = self.review.action_prompt(
            "Herstel de installer", "wiki en memory", "")
        experiment = self.review.action_prompt(
            "Herstel de installer", "wiki en memory", "gevalideerde les")

        self.assertIn("Herstel de installer", baseline)
        self.assertIn("Herstel de installer", experiment)
        self.assertIn("wiki en memory", baseline)
        self.assertIn("wiki en memory", experiment)
        self.assertIn("Geen aanvullende", baseline)
        self.assertIn("gevalideerde les", experiment)

    def test_master_append_is_idempotent_but_never_regenerates_a_case(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "master.jsonl"
            row = {"id": "E-001", "blind": {"id": "E-001"},
                   "key": {"id": "E-001"}}
            self.review.append_unique(path, row)
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.review.append_unique(path, row)
            stored = self.review.load_jsonl(path)
            self.assertEqual(stored, [row])

    def test_record_review_accepts_only_blind_ids_and_four_verdicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blind = root / "blind.jsonl"
            reviews = root / "reviews.jsonl"
            blind.write_text(json.dumps({"id": "E-001"}) + "\n", encoding="utf-8")

            self.review.record_review(
                blind, reviews, case_id="E-001", verdict="both")

            self.assertEqual(self.review.load_jsonl(reviews), [
                {"id": "E-001", "verdict": "both"}])
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.review.record_review(
                    blind, reviews, case_id="E-001", verdict="a_only")
            with self.assertRaisesRegex(ValueError, "invalid verdict"):
                self.review.record_review(
                    blind, root / "other.jsonl", case_id="E-001",
                    verdict="tie")

    def test_next_pair_never_reads_or_returns_the_hidden_key(self):
        pairs = [
            {"id": "E-001", "option_a": "a1", "option_b": "b1"},
            {"id": "E-002", "option_a": "a2", "option_b": "b2"},
        ]
        row, progress = self.review.next_pair(
            pairs, [{"id": "E-001", "verdict": "both"}])

        self.assertEqual(row["id"], "E-002")
        self.assertEqual(progress, {"reviewed": 1, "total": 2, "remaining": 1})
        self.assertNotIn("key", row)


if __name__ == "__main__":
    unittest.main()
