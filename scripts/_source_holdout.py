"""Build privacy-safe, provenance-aware source evaluation manifests.

The raw source remains the authority and stays in the local vault.  A frozen
holdout stores only the query, expected verdict, source coordinates, and the
source hash observed when the case was reviewed.  It is deliberately not a
copy of the source corpus or an answer key containing raw passages.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

from _source_recall import APPROVED_ROOTS, sha256_file

SCHEMA_VERSION = 1
VERDICTS = frozenset(("source", "not_found", "unknown"))
_PUBLIC_KEYS = frozenset((
    "id", "query", "expected_source", "expected_verdict", "expected_hash",
    "expected_windows", "sensitive", "category", "language",
))


def _source_path(value: str, vault: Path) -> tuple[str, Path]:
    """Return a safe vault-relative source path and its resolved file path."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or ":" in raw[:3]:
        raise ValueError("source must be a vault-relative approved path")
    relative = Path(raw)
    if ".." in relative.parts:
        raise ValueError("source path may not escape the vault")
    normalized = relative.as_posix()
    if not any(normalized == root or normalized.startswith(root + "/")
               for root in APPROVED_ROOTS):
        raise ValueError(f"source path is not under an approved raw root: {normalized}")
    root = Path(vault).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("source path may not escape the vault") from exc
    if not path.is_file():
        raise ValueError(f"source file does not exist: {normalized}")
    if ".redacted." in path.name.lower() or path.name.lower().endswith(".redacted"):
        raise ValueError("redacted source cannot be a positive fixture")
    return normalized, path


def _window(value, text_length: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError("window must be an object")
    try:
        start = int(value["start"])
        end = int(value["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("window requires integer start and end") from exc
    if start < 0 or end <= start or end > text_length:
        raise ValueError("window is outside the source bounds")
    return {"start": start, "end": end}


def validate_case(case: dict, vault: Path) -> dict:
    """Validate and normalize one reviewed case without returning source text."""
    if not isinstance(case, dict):
        raise ValueError("holdout case must be an object")
    case_id = str(case.get("id") or "").strip()
    query = str(case.get("query") or "").strip()
    if not case_id:
        raise ValueError("case requires id")
    if not query:
        raise ValueError("case requires query")

    expected_source = case.get("expected_source")
    if expected_source is not None and not str(expected_source).strip():
        expected_source = None
    verdict = str(case.get("expected_verdict") or "").strip().lower()
    if expected_source is None:
        if verdict not in {"not_found", "unknown"}:
            raise ValueError("expected_verdict must be not_found or unknown when expected_source is empty")
        if case.get("expected_windows"):
            raise ValueError("negative fixture cannot contain expected windows")
        return _safe_public_case(case, {
            "id": case_id, "query": query, "expected_source": None,
            "expected_verdict": verdict, "expected_hash": None,
            "expected_windows": [],
        })

    if bool(case.get("sensitive")):
        raise ValueError("sensitive fixture cannot expose a positive source")
    if verdict and verdict != "source":
        raise ValueError("positive fixture must have expected_verdict=source")
    normalized, path = _source_path(str(expected_source), Path(vault))
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("expected source is unreadable as UTF-8 text") from exc
    windows = case.get("expected_windows") or []
    if not isinstance(windows, list) or not windows:
        raise ValueError("positive fixture requires at least one expected window")
    normalized_windows = [_window(item, len(text)) for item in windows]
    expected_hash = sha256_file(path)
    supplied_hash = str(case.get("expected_hash") or "").strip()
    if supplied_hash and supplied_hash != expected_hash:
        raise ValueError("expected_hash does not match the current source")
    return _safe_public_case(case, {
        "id": case_id, "query": query, "expected_source": normalized,
        "expected_verdict": "source", "expected_hash": expected_hash,
        "expected_windows": normalized_windows,
    })


def _safe_public_case(original: dict, fields: dict) -> dict:
    """Keep only explicitly harmless case metadata; drop raw payload fields."""
    result = dict(fields)
    for key in ("sensitive", "category", "language"):
        if key in original:
            result[key] = original[key]
    return {key: result[key] for key in _PUBLIC_KEYS if key in result}


def freeze_manifest(cases: list[dict], vault: Path, output: Path) -> dict:
    """Validate cases and atomically write a versioned, content-safe manifest."""
    normalized = []
    seen = set()
    for case in cases:
        item = validate_case(case, Path(vault))
        if item["id"] in seen:
            raise ValueError(f"duplicate holdout case id: {item['id']}")
        seen.add(item["id"])
        normalized.append(item)
    normalized.sort(key=lambda item: item["id"])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cases": normalized,
        "counts": {
            "total": len(normalized),
            "source": sum(item["expected_verdict"] == "source" for item in normalized),
            "not_found": sum(item["expected_verdict"] == "not_found" for item in normalized),
            "unknown": sum(item["expected_verdict"] == "unknown" for item in normalized),
        },
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, target)
    return payload


def load_manifest(path: Path) -> dict:
    """Load and minimally validate a frozen manifest for evaluation tooling."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("cases"), list):
        raise ValueError("unsupported or malformed source holdout manifest")
    return payload


def oracle_report(manifest: dict, vault: Path) -> dict:
    """Report the current evidence ceiling using aggregates only.

    A positive case is answerable only while its approved source exists, its
    frozen hash still matches, and all frozen windows remain in bounds. The
    report intentionally omits case ids and queries so it can be shared as
    evaluation evidence without exporting the reviewed question set.
    """
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported source holdout manifest")
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise ValueError("source holdout manifest cases must be a list")
    verdicts = Counter()
    reasons = Counter()
    answerable = 0
    for case in cases:
        verdict = str(case.get("expected_verdict") or "").strip().lower()
        verdicts[verdict] += 1
        if verdict != "source":
            continue
        try:
            _normalized, path = _source_path(case.get("expected_source"), Path(vault))
        except ValueError:
            reasons["missing_or_unapproved_source"] += 1
            continue
        expected_hash = str(case.get("expected_hash") or "").strip()
        if not expected_hash:
            reasons["missing_hash"] += 1
            continue
        if sha256_file(path) != expected_hash:
            reasons["hash_mismatch"] += 1
            continue
        try:
            text_length = len(path.read_text(encoding="utf-8"))
            for item in case.get("expected_windows") or []:
                _window(item, text_length)
        except (OSError, UnicodeError):
            reasons["unreadable_source"] += 1
            continue
        except ValueError:
            reasons["window_out_of_bounds"] += 1
            continue
        answerable += 1
    positive = verdicts["source"]
    return {
        "schema_version": SCHEMA_VERSION,
        "verdicts": {key: verdicts[key] for key in ("source", "not_found", "unknown")},
        "oracle": {
            "positive_cases": positive,
            "answerable_positive": answerable,
            "unrecoverable_positive": positive - answerable,
            "ceiling": (answerable / positive) if positive else None,
            "reasons": dict(sorted(reasons.items())),
        },
    }
