"""Content-safe selection helpers for sparse-first source calibration."""
from __future__ import annotations

import math
import re


def _query(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _source_path(value) -> str:
    return str(value or "").split("#", 1)[0].strip().replace("\\", "/").casefold()


def assert_independent_source_cases(development, frozen) -> None:
    """Reject direct id, normalized-query, or expected-document overlap."""
    development = list(development)
    frozen = list(frozen)
    frozen_ids = {str(case.get("id") or case.get("case_id") or "").casefold()
                  for case in frozen}
    frozen_queries = {_query(case.get("query")) for case in frozen}
    frozen_sources = {_source_path(case.get("expected_source")) for case in frozen}
    frozen_sources.discard("")
    for case in development:
        case_id = str(case.get("id") or case.get("case_id") or "").strip()
        if case_id.casefold() in frozen_ids:
            raise ValueError(f"case id overlap: {case_id}")
        if _query(case.get("query")) in frozen_queries:
            raise ValueError(f"query overlap: {case_id or '<unknown>'}")
        source = _source_path(case.get("expected_source"))
        if source and source in frozen_sources:
            raise ValueError(f"source overlap: {case_id or '<unknown>'}: {source}")


def _finite(value, *, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _score(trial: dict, *, safe: bool) -> tuple:
    hit5 = _finite((trial.get("retrieval") or {}).get("hit@5"), fallback=-1.0)
    passage = _finite(trial.get("passage_hit@5"), fallback=-1.0)
    citation = _finite(trial.get("citation_precision"), fallback=-1.0)
    specificity = _finite(trial.get("no_hit_specificity"), fallback=-1.0)
    p95 = _finite((trial.get("warm_latency") or {}).get("p95_ms"),
                  fallback=math.inf)
    cache_bytes = int(trial.get("cache_bytes") or 0)
    configuration = trial.get("configuration") or {}
    compactness = (
        -int(configuration.get("candidate_docs") or 0),
        -int(configuration.get("max_passages") or 0),
        _finite(configuration.get("min_cos"), fallback=-1.0),
    )
    if safe:
        return (hit5, passage, citation, specificity, -p95, -cache_bytes, *compactness)
    return (specificity, -p95, hit5, passage, citation, -cache_bytes, *compactness)


def select_configuration(trials, *, minimum_specificity: float = 0.95,
                         maximum_warm_p95_ms: float = 2000.0) -> dict:
    """Select one development configuration without consulting the holdout."""
    rows = list(trials)
    if not rows:
        raise ValueError("source calibration requires at least one trial")
    safe = [row for row in rows
            if _finite(row.get("no_hit_specificity"), fallback=-1.0)
            >= float(minimum_specificity)
            and _finite((row.get("warm_latency") or {}).get("p95_ms"),
                        fallback=math.inf) < float(maximum_warm_p95_ms)]
    if safe:
        selected = max(safe, key=lambda row: _score(row, safe=True))
        passed = True
        reason = "max_recall_subject_to_safety_and_latency"
    else:
        selected = max(rows, key=lambda row: _score(row, safe=False))
        passed = False
        reason = "best_available_no_safe_trial"
    return {
        "selection_source": "development_only",
        "development_constraints_pass": passed,
        "reason": reason,
        "constraints": {
            "minimum_specificity": float(minimum_specificity),
            "maximum_warm_p95_ms": float(maximum_warm_p95_ms),
        },
        "trial_count": len(rows),
        "selected": selected,
    }
