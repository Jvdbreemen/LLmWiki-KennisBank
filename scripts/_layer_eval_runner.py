#!/usr/bin/env python3
"""Small, content-safe adapters from holdout cases to evaluation aggregates."""
from __future__ import annotations

import _layer_eval


def _paired(baseline, experiment):
    if baseline is None or experiment is None:
        return None
    return _layer_eval.paired_binary_delta(baseline, experiment)


def evaluate_source(cases, retrieve, *, answer_baseline=None,
                    answer_experiment=None) -> dict:
    rows = []
    provenance = []
    conflict_total = 0
    conflict_correct = 0
    for case in cases:
        hits = list(retrieve(case) or [])
        expected = case.get("expected_source")
        ids = [hit.get("source_path") for hit in hits]
        rows.append({"expected": expected, "hits": ids})
        if "expected_conflict" in case:
            conflict_total += 1
            observed = any(bool(hit.get("conflict")) for hit in hits)
            if observed == bool(case.get("expected_conflict")):
                conflict_correct += 1
        for hit in hits:
            provenance.append(bool(hit.get("fresh", False) and hit.get("source_hash")
                                   and int(hit.get("end", 0)) >= int(hit.get("start", 0))
                                   and hit.get("passage", "")))
    metrics = _layer_eval.retrieval_metrics(rows, cutoffs=(1, 5))
    return {
        "retrieval": metrics,
        "provenance_precision": sum(provenance) / len(provenance) if provenance else 1.0,
        "conflict_handling": {
            "n": conflict_total,
            "accuracy": (conflict_correct / conflict_total) if conflict_total else None,
        },
        "answer_delta": _paired(answer_baseline, answer_experiment),
    }


def evaluate_experience(cases, retrieve, *, action_baseline=None,
                        action_experiment=None) -> dict:
    rows = []
    failures = []
    evidence = []
    leakage = 0
    false_warnings = 0
    warning_probes = 0
    reuse_total = 0
    reuse_correct = 0
    failure_total = 0
    failure_correct = 0
    calibration_total = 0
    calibration_correct = 0
    unsupported_lessons = 0
    for case in cases:
        hits = list(retrieve(case) or [])
        expected = case.get("expected_experience")
        validated = [hit for hit in hits if hit.get("status") == "validated"]
        rows.append({"expected": expected,
                     "hits": [hit.get("experience_id") for hit in validated]})
        if expected is not None:
            reuse_total += 1
            if expected in [hit.get("experience_id") for hit in validated]:
                reuse_correct += 1
        if case.get("expected_attempt_state", case.get("expected_state")) == "failure":
            failures.append(rows[-1])
            failure_total += 1
            if expected in rows[-1]["hits"]:
                failure_correct += 1
        if expected is not None and case.get("expected_state") not in {None, "unknown"}:
            calibration_total += 1
            if any(hit.get("experience_id") == expected
                   and hit.get("outcome_state") == case.get("expected_state")
                   for hit in validated):
                calibration_correct += 1
        if expected is None:
            warning_probes += 1
            if hits:
                false_warnings += 1
        for hit in hits:
            if hit.get("status") != "validated":
                leakage += 1
            if not hit.get("source_refs") or not hit.get("outcome_refs"):
                unsupported_lessons += 1
            if hit.get("status") == "validated":
                evidence.append(bool(hit.get("source_refs") and hit.get("outcome_refs")))
    metrics = _layer_eval.retrieval_metrics(rows, cutoffs=(1, 3))
    failure_metrics = _layer_eval.retrieval_metrics(failures, cutoffs=(3,))
    return {
        "retrieval": metrics,
        "failure_hit@3": failure_metrics["hit@3"],
        "useful_reuse@3": reuse_correct / reuse_total if reuse_total else 0.0,
        "repeated_failure_rate": failure_correct / failure_total if failure_total else 0.0,
        "outcome_calibration": (calibration_correct / calibration_total
                                 if calibration_total else 0.0),
        "unsupported_lessons": unsupported_lessons,
        "evidence_precision": sum(evidence) / len(evidence) if evidence else 1.0,
        "candidate_leakage": leakage,
        "false_warning_rate": false_warnings / warning_probes if warning_probes else 0.0,
        "action_delta": _paired(action_baseline, action_experiment),
    }
