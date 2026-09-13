"""Content-safe evidence-packet builder contracts."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("kb_layer_eval", SCRIPTS / "kb-layer-eval.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
import _layer_eval as le  # noqa: E402


def _good_source():
    value = le.source_gate_input_template()
    value.update({"positive_n": 50, "negative_n": 10, "hit@5": 0.8,
                  "lexical_hit@5": 0.6, "provenance_precision": 1.0,
                  "no_hit_specificity": 0.95, "normal_p50_delta_ms": 0.0,
                  "normal_p95_delta_ms": 0.0, "source_p95_ms": 500.0,
                  "rebuild_preserved": True, "answer_pairs_n": 50,
                  "answer_correctness_delta": 0.10})
    return value


def _good_experience():
    value = le.experience_gate_input_template()
    value.update({"labelled_n": 60, "validated_hit@3": 0.8,
                  "lexical_hit@3": 0.6, "failure_hit@3": 0.8,
                  "evidence_precision": 1.0, "candidate_leakage": 0,
                  "false_warning_rate": 0.1, "advisory_precision": 0.9,
                  "normal_p50_delta_ms": 0.0, "normal_p95_delta_ms": 0.0,
                  "action_pairs_n": 60, "action_correctness_delta": 0.10})
    return value


class LayerEvalCliTest(unittest.TestCase):
    def test_build_report_contains_six_arm_coverage_decisions_and_latency(self):
        payload = {
            "arms": {name: {"status": "measured"} for name in "ABCDEF"},
            "source": _good_source(), "experience": _good_experience(),
            "latency_ms": {"normal": [3, 7, 9], "source": [100, 250],
                           "experience": [80, 120]},
        }
        report = cli.build_report(payload)
        self.assertEqual(report["decisions"]["source"], "go")
        self.assertEqual(report["decisions"]["experience"], "go")
        self.assertEqual(report["arms"]["missing"], [])
        self.assertEqual(report["latency_ms"]["normal"]["p50_ms"], 7.0)
        self.assertNotIn("prompt", json.dumps(report).lower())

    def test_build_report_keeps_missing_experimental_arm_explicit(self):
        payload = {"arms": {"A": {}, "B": {}, "C": {}, "D": {},
                             "omissions": {"E": "no labelled experience holdout",
                                            "F": "research-only arm not run"}},
                   "source": le.source_gate_input_template(),
                   "experience": le.experience_gate_input_template()}
        report = cli.build_report(payload)
        self.assertEqual(report["arms"]["missing"], ["E", "F"])
        self.assertEqual(report["decisions"]["source"], "hold")

    def test_cli_writes_only_the_requested_evidence_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observations = root / "observations.json"
            output = root / "report.json"
            observations.write_text(json.dumps({
                "arms": {name: {} for name in "ABCDEF"},
                "source": le.source_gate_input_template(),
                "experience": le.experience_gate_input_template(),
            }), encoding="utf-8")
            self.assertEqual(cli.main(["--observations", str(observations),
                                       "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
