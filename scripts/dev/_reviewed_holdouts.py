"""Promote human-reviewed cases into private evaluation inputs.

The interactive review file may contain private answers and source details.  The
helpers below copy only the fields needed by the existing source and experience
evaluation contracts.  They deliberately require a separate normalized outcome
state for experience cases: a prose outcome is not silently treated as evidence
for ``success`` or ``failure``.
"""
from __future__ import annotations

import re


EXPERIENCE_STATES = frozenset(("success", "failure", "partial", "mixed", "unknown"))
RESOLUTION_STATES = frozenset(("not_applicable", "unresolved", "diagnosed",
                               "fix_proposed", "fix_validated",
                               "corrected_with_cost"))
SOURCE_VERDICTS = {"found": "source", "not_found": "not_found", "unknown": "unknown"}


def _reviewed(case: dict, layer: str) -> bool:
    return (case.get("layer") == layer
            and str(case.get("review_status") or "").lower() == "reviewed"
            and str(case.get("review_decision") or "").lower() == "keep")


def _selected(rows, layer: str) -> list[dict]:
    selected = [row for row in rows if row.get("layer") == layer]
    for row in selected:
        if not _reviewed(row, layer):
            raise ValueError(f"{layer} cases must be reviewed and kept")
    return selected


def _unique(case_id: str, seen: set[str]) -> str:
    value = str(case_id or "").strip()
    if not value:
        raise ValueError("reviewed case requires case_id")
    if value in seen:
        raise ValueError(f"duplicate reviewed case id: {value}")
    seen.add(value)
    return value


def prepare_source_cases(rows) -> list[dict]:
    """Map reviewed source rows to ``_source_holdout`` input records."""
    result = []
    seen: set[str] = set()
    for row in _selected(rows, "source_recall"):
        case_id = _unique(row.get("case_id"), seen)
        verdict = SOURCE_VERDICTS.get(str(row.get("gold_verdict") or "").lower())
        if verdict is None:
            raise ValueError(f"unsupported source verdict for {case_id}")
        expected_source = row.get("expected_source") if verdict == "source" else None
        expected_hash = row.get("expected_source_hash") if verdict == "source" else None
        expected_windows = list(row.get("expected_windows") or []) if verdict == "source" else []
        if verdict == "source" and (not expected_source or not expected_hash or not expected_windows):
            raise ValueError(f"positive source case lacks provenance: {case_id}")
        result.append({
            "id": case_id,
            "query": str(row.get("query") or "").strip(),
            "expected_source": expected_source,
            "expected_verdict": verdict,
            "expected_hash": expected_hash,
            "expected_windows": expected_windows,
            "category": row.get("category"),
            "language": row.get("language"),
            "sensitive": bool(row.get("sensitive", False)),
        })
    return result


def _slug(case_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", case_id.lower()).strip("-")
    return value or "case"


def _source_refs(sources) -> list[str]:
    refs = []
    for source in sources or []:
        path = str(source.get("path") or "").strip().replace("\\", "/")
        digest = str(source.get("hash") or "").strip()
        windows = source.get("windows") or []
        if not path or not digest.startswith("sha256:") or not windows:
            raise ValueError("experience evidence requires path, sha256 hash, and windows")
        for window in windows:
            try:
                start = int(window["start"])
                end = int(window["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("experience evidence window requires integer bounds") from exc
            if start < 0 or end <= start:
                raise ValueError("experience evidence window is invalid")
            refs.append(f"{path}#{start}:{end}@{digest}")
    if not refs:
        raise ValueError("validated experience requires evidence sources")
    return refs


def _text(value) -> str:
    if isinstance(value, dict):
        return " ".join(part for item in value.values() if (part := _text(item)))
    if isinstance(value, (list, tuple)):
        return "; ".join(part for item in value if (part := _text(item)))
    return str(value or "").strip()


def _first(expected: dict, *keys: str) -> str:
    for key in keys:
        value = _text(expected.get(key))
        if value:
            return value
    return ""


def prepare_experience_cases(rows, *, states: dict[str, str],
                             attempt_states: dict[str, str] | None = None,
                             resolution_states: dict[str, str] | None = None) -> list[dict]:
    """Map reviewed experience rows to ``_layer_eval_runner`` inputs.

    ``states`` is intentionally separate from the interactive prose review.  It
    must be reviewed as its own private label set before the resulting records
    can claim validated outcome evidence.
    """
    result = []
    seen: set[str] = set()
    attempt_states = attempt_states or {}
    resolution_states = resolution_states or {}
    for row in _selected(rows, "experience_recall"):
        case_id = _unique(row.get("case_id"), seen)
        state = str(states.get(case_id) or row.get("expected_state") or "").lower()
        if state not in EXPERIENCE_STATES:
            raise ValueError(f"normalized experience state required for {case_id}")
        attempt_state = str(attempt_states.get(case_id)
                            or row.get("expected_attempt_state") or state).lower()
        resolution_state = str(resolution_states.get(case_id)
                               or row.get("expected_resolution_state")
                               or "not_applicable").lower()
        if attempt_state not in EXPERIENCE_STATES:
            raise ValueError(f"normalized attempt state required for {case_id}")
        if resolution_state not in RESOLUTION_STATES:
            raise ValueError(f"normalized resolution state required for {case_id}")
        expected = row.get("expected_experience")
        if expected is None:
            if state != "unknown":
                raise ValueError(f"empty experience must use unknown state: {case_id}")
            result.append({
                "id": case_id,
                "query": str(row.get("query") or "").strip(),
                "expected_experience": None,
                "expected_state": state,
                "expected_attempt_state": attempt_state,
                "expected_resolution_state": resolution_state,
                "records": [],
                "category": row.get("category"),
                "language": row.get("language"),
            })
            continue
        if not isinstance(expected, dict):
            raise ValueError(f"structured expected_experience required for {case_id}")
        if state == "unknown":
            raise ValueError(f"validated experience cannot use unknown state: {case_id}")
        source_refs = _source_refs(row.get("evidence_sources"))
        experience_id = "reviewed-experience-" + _slug(case_id)
        outcome_id = "reviewed-outcome-" + _slug(case_id)
        scope = _first(expected, "scope", "applicability") or str(
            row.get("category") or "reviewed experience")
        outcome = _first(expected, "outcome", "observed_result", "result")
        action = _first(
            expected, "recommended_action", "fix", "safe_action", "repair",
            "preventive_action", "recovery", "decision_rule", "procedure",
            "recommended_procedure", "lesson") or _text(expected)
        tradeoff = _first(expected, "tradeoff", "limitation", "risk")
        if not action or not scope or not outcome:
            raise ValueError(f"experience proposition is incomplete: {case_id}")
        lesson = _first(expected, "lesson") or action
        if tradeoff:
            lesson = f"{lesson} Trade-off: {tradeoff}"
        record = {
            "experience_id": experience_id,
            "status": "validated",
            "outcome_state": state,
            "attempt_state": attempt_state,
            "resolution_state": resolution_state,
            "situation": _text(expected),
            "approach": action,
            "action": action,
            "observed_result": outcome,
            "lesson": lesson,
            "applicability": scope,
            "source_refs": source_refs,
            "outcome_refs": [outcome_id],
        }
        result.append({
            "id": case_id,
            "query": str(row.get("query") or "").strip(),
            "expected_experience": experience_id,
            "expected_state": state,
            "expected_attempt_state": attempt_state,
            "expected_resolution_state": resolution_state,
            "records": [record],
            "category": row.get("category"),
            "language": row.get("language"),
        })
    return result


def prepare_experience_negative_probes(source_cases) -> list[dict]:
    """Reuse reviewed source abstentions as clearly labelled cross-layer probes."""
    probes = []
    for case in source_cases:
        if case.get("expected_verdict") == "source":
            continue
        probes.append({
            "id": "XP-" + str(case["id"]),
            "query": str(case.get("query") or "").strip(),
            "expected_experience": None,
            "expected_state": "unknown",
            "records": [],
            "category": "cross_layer_source_abstention",
            "language": case.get("language"),
            "probe_origin": "reviewed_source_negative",
        })
    return probes
