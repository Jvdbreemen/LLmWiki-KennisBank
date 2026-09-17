"""Content-safe helpers for independent advisory calibration."""
from __future__ import annotations

import math
import re


def _query(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _source_path(value) -> str:
    return str(value or "").split("#", 1)[0].strip().replace("\\", "/").casefold()


def _source_paths(case: dict) -> set[str]:
    paths = set()
    if case.get("expected_source"):
        paths.add(_source_path(case["expected_source"]))
    for source in case.get("evidence_sources") or []:
        if isinstance(source, dict) and source.get("path"):
            paths.add(_source_path(source["path"]))
    for record in case.get("records") or []:
        for ref in record.get("source_refs") or []:
            paths.add(_source_path(ref))
    return {path for path in paths if path}


def assert_independent(development, frozen) -> None:
    """Reject direct query, id, or evidence-source overlap between splits."""
    development = list(development)
    frozen = list(frozen)
    frozen_ids = {str(case.get("id") or case.get("case_id") or "").casefold()
                  for case in frozen}
    frozen_queries = {_query(case.get("query")) for case in frozen}
    frozen_sources = set().union(*(_source_paths(case) for case in frozen)) if frozen else set()
    for case in development:
        case_id = str(case.get("id") or case.get("case_id") or "").casefold()
        if case_id and case_id in frozen_ids:
            raise ValueError(f"case id overlap: {case_id}")
        query = _query(case.get("query"))
        if query and query in frozen_queries:
            raise ValueError(f"query overlap: {case_id or '<unknown>'}")
        overlap = _source_paths(case) & frozen_sources
        if overlap:
            raise ValueError(
                f"source overlap: {case_id or '<unknown>'}: {sorted(overlap)[0]}")


def _metrics(observations: list[dict], threshold: float) -> dict:
    positives = [row for row in observations if row.get("expected_experience") is not None]
    negatives = [row for row in observations if row.get("expected_experience") is None]
    warnings = []
    correct = 0
    false_warnings = 0
    for row in observations:
        score = row.get("score")
        warned = (row.get("candidate_experience") is not None
                  and score is not None and float(score) >= threshold)
        if not warned:
            continue
        warnings.append(row)
        if row.get("expected_experience") is None:
            false_warnings += 1
        elif row.get("candidate_experience") == row.get("expected_experience"):
            correct += 1
    return {
        "threshold": threshold,
        "positive_n": len(positives),
        "negative_n": len(negatives),
        "warnings": len(warnings),
        "correct_warnings": correct,
        "false_warnings": false_warnings,
        "positive_recall": correct / len(positives) if positives else 0.0,
        "precision": correct / len(warnings) if warnings else 0.0,
        "false_warning_rate": false_warnings / len(negatives) if negatives else 0.0,
    }


def calibrate_threshold(observations, *, thresholds,
                        min_precision: float = 0.9,
                        max_false_warning_rate: float = 0.1) -> dict:
    """Select one threshold from development observations only.

    Eligible thresholds satisfy both safety bounds. Selection then maximizes
    positive recall, precision, and finally the threshold itself for a stable,
    conservative tie break.
    """
    rows = list(observations)
    seen = set()
    for row in rows:
        case_id = str(row.get("id") or "").strip()
        if not case_id or case_id in seen:
            raise ValueError("development observations require unique ids")
        seen.add(case_id)
    values = sorted({float(value) for value in thresholds})
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("calibration thresholds must be finite")
    trials = [_metrics(rows, value) for value in values]
    eligible = [trial for trial in trials
                if trial["precision"] >= min_precision
                and trial["false_warning_rate"] <= max_false_warning_rate]
    result = {
        "selection_source": "development_only",
        "constraints": {
            "min_precision": float(min_precision),
            "max_false_warning_rate": float(max_false_warning_rate),
        },
        "trials": trials,
    }
    if not eligible:
        result.update({
            "selected_threshold": None,
            "selected": None,
            "reason": "no_threshold_meets_safety_constraints",
        })
        return result
    selected = max(eligible, key=lambda trial: (
        trial["positive_recall"], trial["precision"],
        -trial["false_warning_rate"], trial["threshold"]))
    result.update({
        "selected_threshold": selected["threshold"],
        "selected": selected,
        "reason": "max_recall_subject_to_safety_constraints",
    })
    return result


def compare_to_lexical(hybrid: dict, lexical: dict) -> dict:
    """Require an advisory-recall gain that lexical retrieval cannot explain."""
    delta = float(hybrid.get("positive_recall", 0.0)) - float(
        lexical.get("positive_recall", 0.0))
    passes = delta > 0.0
    return {
        "passes": passes,
        "delta": delta,
        "reason": "hybrid_recall_gain" if passes else "no_hybrid_recall_gain",
    }
