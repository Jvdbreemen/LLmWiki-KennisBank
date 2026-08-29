#!/usr/bin/env python3
"""Pure evaluation helpers for source and experience recall experiments.

This module deliberately has no vault, model, or telemetry dependency. It owns
the pre-registered arithmetic and gates; experiment runners provide observations
and write reports elsewhere. Keeping the rules pure prevents a runner from
quietly changing the winner rule after seeing its results.
"""
from __future__ import annotations

import os
import random
import math
from contextlib import contextmanager

ARM_NAMES = ("A", "B", "C", "D", "E", "F")


def retrieval_metrics(cases, cutoffs=(1, 3, 5)) -> dict:
    """Return deterministic rank metrics for labelled retrieval cases.

    Each case contains ``expected`` (an id or ``None``) and ordered ``hits``.
    Negative cases score no-hit precision: the fraction for which retrieval
    correctly returned no result.
    """
    rows = list(cases)
    positives = [row for row in rows if row.get("expected") is not None]
    negatives = [row for row in rows if row.get("expected") is None]
    result = {
        "n": len(rows),
        "positive_n": len(positives),
        "negative_n": len(negatives),
    }
    for cutoff in cutoffs:
        found = sum(
            1 for row in positives
            if row.get("expected") in list(row.get("hits") or [])[:cutoff]
        )
        result[f"hit@{cutoff}"] = found / len(positives) if positives else 0.0
    reciprocal = []
    for row in positives:
        try:
            rank = list(row.get("hits") or []).index(row.get("expected")) + 1
        except ValueError:
            rank = 0
        reciprocal.append((1.0 / rank) if rank else 0.0)
    result["mrr"] = sum(reciprocal) / len(reciprocal) if reciprocal else 0.0
    correct_empty = sum(1 for row in negatives if not row.get("hits"))
    result["no_hit_precision"] = (
        correct_empty / len(negatives) if negatives else 0.0
    )
    return result


def paired_binary_delta(baseline, experiment, *, bootstrap: int = 1000,
                        seed: int = 211) -> dict:
    """Compare paired correctness labels and return a reproducible percentile CI."""
    baseline, experiment = list(baseline), list(experiment)
    if len(baseline) != len(experiment):
        raise ValueError("paired arms must have equal length")
    n = len(baseline)
    if not n:
        return {"n": 0, "baseline_correct": 0, "experiment_correct": 0,
                "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rows = [(bool(left), bool(right)) for left, right in zip(baseline, experiment)]
    delta = sum(right for _left, right in rows) / n - sum(left for left, _right in rows) / n
    if bootstrap <= 0:
        bootstrap = 1
    rng = random.Random(seed)
    samples = []
    for _ in range(bootstrap):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(right for _left, right in sample) / n -
                       sum(left for left, _right in sample) / n)
    samples.sort()
    low = samples[max(0, int(0.025 * len(samples)) - 1)]
    high = samples[min(len(samples) - 1, int(0.975 * len(samples)))]
    return {"n": n, "baseline_correct": sum(left for left, _right in rows),
            "experiment_correct": sum(right for _left, right in rows),
            "delta": delta, "ci_low": low, "ci_high": high}


def source_gate_input_template() -> dict:
    return {
        "positive_n": 0,
        "negative_n": 0,
        "hit@5": 0.0,
        "lexical_hit@5": 0.0,
        "provenance_precision": 0.0,
        "no_hit_specificity": 0.0,
        "normal_p50_delta_ms": float("inf"),
        "normal_p95_delta_ms": float("inf"),
        "source_p95_ms": float("inf"),
        "rebuild_preserved": False,
        "answer_pairs_n": 0,
        "answer_correctness_delta": 0.0,
    }


def experience_gate_input_template() -> dict:
    return {
        "labelled_n": 0,
        "validated_hit@3": 0.0,
        "lexical_hit@3": 0.0,
        "failure_hit@3": 0.0,
        "evidence_precision": 0.0,
        "candidate_leakage": 0,
        "false_warning_rate": 1.0,
        "advisory_precision": 0.0,
        "normal_p50_delta_ms": float("inf"),
        "normal_p95_delta_ms": float("inf"),
        "action_pairs_n": 0,
        "action_correctness_delta": 0.0,
    }


def _result(checks) -> dict:
    failed = [name for name, passed in checks if not passed]
    return {"passed": not failed, "failed": failed,
            "checks": {name: bool(passed) for name, passed in checks}}


def source_gate(metrics: dict) -> dict:
    """Apply the immutable source-recall winner rule from the research plan."""
    hit = float(metrics.get("hit@5", 0.0))
    lexical = float(metrics.get("lexical_hit@5", 0.0))
    relative = (hit - lexical >= 0.10 - 1e-12) or (lexical >= 0.85 and hit >= lexical)
    checks = [
        ("minimum_positive_sample", int(metrics.get("positive_n", 0)) >= 50),
        ("minimum_negative_sample", int(metrics.get("negative_n", 0)) >= 10),
        ("absolute_hit_at_5", hit >= 0.70),
        ("lexical_delta_or_ceiling", relative),
        ("exact_provenance", float(metrics.get("provenance_precision", 0.0)) == 1.0),
        ("no_hit_specificity", float(metrics.get("no_hit_specificity", 0.0)) >= 0.95),
        ("normal_p50_delta", float(metrics.get("normal_p50_delta_ms", float("inf"))) < 5.0),
        ("normal_p95_delta", float(metrics.get("normal_p95_delta_ms", float("inf"))) < 5.0),
        ("source_p95", float(metrics.get("source_p95_ms", float("inf"))) < 2000.0),
        ("rebuild_preserved", metrics.get("rebuild_preserved") is True),
        ("minimum_paired_answers", int(metrics.get("answer_pairs_n", 0)) >= 50),
        ("answer_correctness_delta", float(metrics.get("answer_correctness_delta", 0.0)) >= 0.10),
    ]
    return _result(checks)


def experience_gate(metrics: dict) -> dict:
    """Apply the immutable experience-recall winner rule."""
    hit = float(metrics.get("validated_hit@3", 0.0))
    lexical = float(metrics.get("lexical_hit@3", 0.0))
    relative = (hit - lexical >= 0.10 - 1e-12) or (lexical >= 0.85 and hit >= lexical)
    checks = [
        ("minimum_labelled_sample", int(metrics.get("labelled_n", 0)) >= 60),
        ("absolute_hit_at_3", hit >= 0.70),
        ("lexical_delta_or_ceiling", relative),
        ("failure_hit_at_3", float(metrics.get("failure_hit@3", 0.0)) >= 0.70),
        ("exact_evidence", float(metrics.get("evidence_precision", 0.0)) == 1.0),
        ("no_candidate_leakage", int(metrics.get("candidate_leakage", 0)) == 0),
        ("false_warning_rate", float(metrics.get("false_warning_rate", 1.0)) <= 0.10),
        ("advisory_precision", float(metrics.get("advisory_precision", 0.0)) >= 0.90),
        ("normal_p50_delta", float(metrics.get("normal_p50_delta_ms", float("inf"))) < 5.0),
        ("normal_p95_delta", float(metrics.get("normal_p95_delta_ms", float("inf"))) < 5.0),
        ("minimum_paired_actions", int(metrics.get("action_pairs_n", 0)) >= 60),
        ("action_correctness_delta", float(metrics.get("action_correctness_delta", 0.0)) >= 0.10),
    ]
    return _result(checks)


def validate_arm_coverage(arms: dict) -> dict:
    """Require all preregistered arms or a non-empty omission reason."""
    arms = dict(arms or {})
    omissions = dict(arms.get("omissions") or {})
    present = sorted(name for name in ARM_NAMES if name in arms)
    missing = [name for name in ARM_NAMES if name not in arms]
    unexplained = [name for name in missing if not str(omissions.get(name) or "").strip()]
    if unexplained:
        raise ValueError("missing arms require an explicit omission reason: "
                         + ", ".join(unexplained))
    return {"required": list(ARM_NAMES), "present": present, "missing": missing,
            "omissions": {name: str(omissions[name]).strip() for name in missing
                          if name in omissions}}


def latency_summary(samples) -> dict:
    """Return deterministic nearest-rank p50/p95 milliseconds."""
    values = sorted(float(value) for value in (samples or []))
    if not values:
        return {"n": 0, "p50_ms": None, "p95_ms": None}
    def percentile(fraction):
        return values[max(0, min(len(values) - 1, math.ceil(fraction * len(values)) - 1))]
    return {"n": len(values), "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95)}


def _decision(gate: dict, *, minimum_checks, safety_checks) -> str:
    if gate["passed"]:
        return "go"
    failed = set(gate["failed"])
    core_sample_checks = {"minimum_positive_sample", "minimum_negative_sample",
                          "minimum_labelled_sample"}
    if failed.intersection(core_sample_checks):
        return "hold"
    if failed.intersection(safety_checks):
        return "reject"
    if failed.intersection(minimum_checks):
        return "hold"
    return "reject"


def decision_table(source_metrics: dict, experience_metrics: dict) -> dict:
    """Apply the preregistered go/hold/reject policy without tuning thresholds."""
    source = source_gate(source_metrics)
    experience = experience_gate(experience_metrics)
    source_minimum = {"minimum_positive_sample", "minimum_negative_sample",
                      "minimum_paired_answers"}
    source_safety = {"exact_provenance", "no_hit_specificity", "normal_p50_delta",
                     "normal_p95_delta", "source_p95", "rebuild_preserved"}
    experience_minimum = {"minimum_labelled_sample", "minimum_paired_actions"}
    experience_safety = {"exact_evidence", "no_candidate_leakage", "false_warning_rate",
                         "advisory_precision", "normal_p50_delta", "normal_p95_delta"}
    return {
        "source": _decision(source, minimum_checks=source_minimum,
                             safety_checks=source_safety),
        "experience": _decision(experience, minimum_checks=experience_minimum,
                                 safety_checks=experience_safety),
        "source_gate": source, "experience_gate": experience,
        "policy": {
            "go": "all preregistered gates pass",
            "hold": "required sample or evidence packet is incomplete",
            "reject": "safety gate or value gate fails with sufficient evidence",
        },
    }


@contextmanager
def evaluation_environment():
    """Disable production usage telemetry for the duration of an eval run."""
    sentinel = object()
    previous = os.environ.get("KB_USAGE_DISABLE", sentinel)
    os.environ["KB_USAGE_DISABLE"] = "1"
    try:
        yield
    finally:
        if previous is sentinel:
            os.environ.pop("KB_USAGE_DISABLE", None)
        else:
            os.environ["KB_USAGE_DISABLE"] = previous
