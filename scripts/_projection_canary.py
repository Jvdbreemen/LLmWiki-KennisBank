#!/usr/bin/env python3
"""Content-safe owner-canary ledger and aggregate gates for deeper recall.

Per-case rows are private and append-only.  They deliberately contain verdicts
and counters rather than prompts, passages, paths, SourceRefs, or lessons.  The
aggregate returned by :func:`aggregate` is safe to copy into repository
evidence, but the JSONL ledger itself belongs inside the configured vault.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1
LAYERS = {"source", "experience"}
ROUTES = {
    "source": {"exact_ref", "lexical_fts"},
    "experience": {"hybrid", "lexical_fallback"},
}

_COMMON_FIELDS = {
    "schema_version", "canary_id", "layer", "route", "observed_at",
    "result_status", "shown_count", "latency_ms", "owner_reviewed",
    "candidate_leakage", "idempotency_key",
}
_LAYER_FIELDS = {
    "source": {"reconstruction_correct", "provenance_correct"},
    "experience": {
        "natural_explicit_use", "useful", "harmful", "evidence_correct",
    },
}
_CONTENT_FIELDS = {
    "prompt", "query", "passage", "lesson", "source_path", "source_ref",
    "source_refs", "outcome_refs", "embedding", "answer", "response",
}


def _truth(value, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("observed_at is required")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc


def validate_record(value: dict) -> dict:
    """Normalize one private verdict row and reject content-bearing fields."""
    record = dict(value or {})
    content = sorted(field for field in record if field.lower() in _CONTENT_FIELDS)
    if content:
        raise ValueError("content field is forbidden in canary ledger: "
                         + ", ".join(content))
    layer = str(record.get("layer") or "").strip().lower()
    if layer not in LAYERS:
        raise ValueError("layer must be source or experience")
    allowed = _COMMON_FIELDS | _LAYER_FIELDS[layer]
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise ValueError("unsupported canary field: " + ", ".join(unknown))
    if int(record.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for field in ("canary_id", "idempotency_key"):
        if not str(record.get(field) or "").strip():
            raise ValueError(f"{field} is required")
    route = str(record.get("route") or "").strip().lower()
    if route not in ROUTES[layer]:
        raise ValueError(f"invalid {layer} route")
    observed = _timestamp(record.get("observed_at"))
    status = str(record.get("result_status") or "").strip().lower()
    if status not in {"ok", "no_hit", "evidence_unavailable"}:
        raise ValueError("invalid result_status")
    shown_count = int(record.get("shown_count", -1))
    leakage = int(record.get("candidate_leakage", -1))
    latency = float(record.get("latency_ms", -1.0))
    if shown_count < 0 or leakage < 0 or not math.isfinite(latency) or latency < 0:
        raise ValueError("counts and latency must be finite and non-negative")
    normalized = {
        "schema_version": SCHEMA_VERSION,
        "canary_id": str(record["canary_id"]).strip(),
        "layer": layer,
        "route": route,
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "result_status": status,
        "shown_count": shown_count,
        "latency_ms": latency,
        "owner_reviewed": _truth(record.get("owner_reviewed"), "owner_reviewed"),
        "candidate_leakage": leakage,
        "idempotency_key": str(record["idempotency_key"]).strip(),
    }
    for field in _LAYER_FIELDS[layer]:
        normalized[field] = _truth(record.get(field), field)
    return normalized


def load_records(path: Path) -> list[dict]:
    if not Path(path).is_file():
        return []
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(validate_record(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid canary row {number}: {exc}") from exc
    keys = [row["idempotency_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate idempotency key in canary ledger")
    return rows


def append_record(path: Path, value: dict) -> bool:
    """Append idempotently through an atomic replacement of the private log."""
    path = Path(path)
    record = validate_record(value)
    rows = load_records(path)
    for existing in rows:
        if existing["idempotency_key"] != record["idempotency_key"]:
            continue
        if existing != record:
            raise ValueError("idempotency key already contains a different canary row")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in [*rows, record]
    )
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
    return True


def _nearest_rank(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1,
                              math.ceil(fraction * len(ordered)) - 1))]


def _gate(checks: list[tuple[str, bool]]) -> tuple[bool, list[str], dict]:
    failed = [name for name, passed in checks if not passed]
    return not failed, failed, {name: bool(passed) for name, passed in checks}


def aggregate(values) -> dict:
    """Return content-free metrics without case ids or idempotency keys."""
    rows = [validate_record(value) for value in values]
    source = [row for row in rows if row["layer"] == "source"]
    experience = [row for row in rows if row["layer"] == "experience"]
    source_eligible = [row for row in source if row["owner_reviewed"]]
    experience_eligible = [row for row in experience
                           if row["owner_reviewed"] and row["natural_explicit_use"]]

    earliest_experience = min((_timestamp(row["observed_at"])
                               for row in experience), default=None)
    source_before = (earliest_experience is None or sum(
        _timestamp(row["observed_at"]) < earliest_experience
        for row in source_eligible
    ) >= 10)

    source_shown = sum(row["shown_count"] for row in source_eligible)
    source_provenance = sum(row["shown_count"] for row in source_eligible
                            if row["provenance_correct"])
    source_reconstructed = sum(bool(row["reconstruction_correct"])
                               for row in source_eligible)
    source_leakage = sum(row["candidate_leakage"] for row in source_eligible)
    source_precision = source_provenance / source_shown if source_shown else 0.0
    source_checks = [
        ("minimum_owner_reconstructions", len(source_eligible) >= 10),
        ("all_reconstructions_correct", source_reconstructed == len(source_eligible)),
        ("provenance_precision", source_precision == 1.0),
        ("candidate_leakage", source_leakage == 0),
    ]
    source_passed, source_failed, source_check_map = _gate(source_checks)

    exp_n = len(experience_eligible)
    useful = sum(row["useful"] for row in experience_eligible)
    harmful = sum(row["harmful"] for row in experience_eligible)
    exp_shown = sum(row["shown_count"] for row in experience_eligible)
    evidence_correct = sum(row["shown_count"] for row in experience_eligible
                           if row["evidence_correct"])
    exp_leakage = sum(row["candidate_leakage"] for row in experience_eligible)
    useful_rate = useful / exp_n if exp_n else 0.0
    harmful_rate = harmful / exp_n if exp_n else 0.0
    evidence_precision = evidence_correct / exp_shown if exp_shown else 0.0
    experience_checks = [
        ("minimum_natural_explicit_reviews", exp_n >= 20),
        ("useful_rate", useful_rate >= 0.70),
        ("harmful_rate", exp_n > 0 and harmful_rate <= 0.05),
        ("evidence_precision", evidence_precision == 1.0),
        ("candidate_leakage", exp_leakage == 0),
        ("source_before_experience", source_before),
    ]
    exp_passed, exp_failed, exp_check_map = _gate(experience_checks)

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "eligible_n": len(source_eligible),
            "shown_passages_n": source_shown,
            "correct_reconstructions_n": source_reconstructed,
            "provenance_precision": source_precision,
            "candidate_leakage": source_leakage,
            "latency_ms": {
                "n": len(source_eligible),
                "p50": _nearest_rank([row["latency_ms"] for row in source_eligible], .50),
                "p95": _nearest_rank([row["latency_ms"] for row in source_eligible], .95),
            },
            "passed": source_passed, "failed": source_failed,
            "checks": source_check_map,
        },
        "experience": {
            "eligible_n": exp_n,
            "useful_n": useful,
            "harmful_n": harmful,
            "useful_rate": useful_rate,
            "harmful_rate": harmful_rate,
            "shown_hits_n": exp_shown,
            "evidence_precision": evidence_precision,
            "candidate_leakage": exp_leakage,
            "latency_ms": {
                "n": exp_n,
                "p50": _nearest_rank([row["latency_ms"] for row in experience_eligible], .50),
                "p95": _nearest_rank([row["latency_ms"] for row in experience_eligible], .95),
            },
            "passed": exp_passed, "failed": exp_failed,
            "checks": exp_check_map,
        },
        "sequence": {"source_before_experience": source_before},
    }
