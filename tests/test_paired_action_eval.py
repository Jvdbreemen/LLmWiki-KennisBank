"""Contracts for blinded experience-versus-baseline action judgments."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "_paired_action_eval.py"


def load_module():
    spec = importlib.util.spec_from_file_location("paired_action_eval", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PairedActionEvalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paired = load_module()

    def test_assignment_is_deterministic_and_balanced_for_sixty_cases(self):
        ids = [f"E-{number:03d}" for number in range(1, 61)]

        first = self.paired.assignment_map(ids, seed=224)
        second = self.paired.assignment_map(reversed(ids), seed=224)

        self.assertEqual(first, second)
        self.assertEqual(sum(arm == "baseline" for arm in first.values()), 30)
        self.assertEqual(sum(arm == "experience" for arm in first.values()), 30)

    def test_blind_pair_contains_no_arm_identity_and_key_binds_hashes(self):
        blind, key = self.paired.make_pair(
            case={
                "id": "E-001",
                "query": "Hoe herstel ik dit veilig?",
                "records": [{
                    "observed_result": "De eerste poging mislukte.",
                    "lesson": "Gebruik een begrensde rollback.",
                    "applicability": "Installers",
                    "source_refs": ["raw#1"],
                }],
            },
            baseline="Doe een onbeperkte retry.",
            experience="Gebruik een begrensde rollback.",
            a_arm="experience",
            common_context_sha256="sha256:common",
            experience_ids=["lesson-1"],
            model="qwen3.5:4b",
        )

        self.assertEqual(blind["option_a"], "Gebruik een begrensde rollback.")
        self.assertEqual(blind["option_b"], "Doe een onbeperkte retry.")
        self.assertNotIn("baseline", blind)
        self.assertNotIn("experience", blind)
        self.assertEqual(key["a_arm"], "experience")
        self.assertEqual(key["b_arm"], "baseline")
        self.paired.verify_pair(blind, key)

    def test_scoring_maps_four_verdicts_back_to_the_hidden_arms(self):
        pairs = []
        keys = []
        reviews = []
        fixtures = [
            ("one", "baseline", "a_only"),
            ("two", "experience", "a_only"),
            ("three", "baseline", "both"),
            ("four", "experience", "neither"),
        ]
        for case_id, a_arm, verdict in fixtures:
            pair, key = self.paired.make_pair(
                case={"id": case_id, "query": case_id, "records": [{
                    "observed_result": "result", "lesson": "lesson",
                    "applicability": "scope", "source_refs": ["raw#1"]}]},
                baseline=f"baseline {case_id}",
                experience=f"experience {case_id}",
                a_arm=a_arm,
                common_context_sha256="sha256:common",
                experience_ids=[case_id], model="model")
            pairs.append(pair)
            keys.append(key)
            reviews.append({"id": case_id, "verdict": verdict})

        result = self.paired.score(pairs, keys, reviews, bootstrap=200)

        self.assertEqual(result["n"], 4)
        self.assertEqual(result["baseline_correct"], 2)
        self.assertEqual(result["experience_correct"], 2)
        self.assertEqual(result["delta"], 0.0)
        self.assertEqual(result["verdicts"], {
            "a_only": 2, "b_only": 0, "both": 1, "neither": 1})

    def test_tampered_option_is_rejected_before_scoring(self):
        blind, key = self.paired.make_pair(
            case={"id": "x", "query": "q", "records": [{
                "observed_result": "r", "lesson": "l",
                "applicability": "a", "source_refs": ["s"]}]},
            baseline="base", experience="exp", a_arm="baseline",
            common_context_sha256="sha256:common", experience_ids=["x"],
            model="model")
        blind["option_a"] = "changed"

        with self.assertRaisesRegex(ValueError, "hash"):
            self.paired.verify_pair(blind, key)


if __name__ == "__main__":
    unittest.main()
