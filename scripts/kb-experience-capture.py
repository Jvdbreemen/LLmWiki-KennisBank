#!/usr/bin/env python3
"""Append one explicit, source-grounded candidate event to the private ledger.

Input is one JSON object on stdin. The command creates exact SourceRefs from
vault-relative ranges before writing and returns identifiers/counts only. It
never writes a retrieval projection or promotes its own interpretation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience  # noqa: E402
import _settings  # noqa: E402
import _source_ref  # noqa: E402

CAPTURE_SCHEMA_VERSION = "1"
_EVENT_TYPES = {
    "task_context", "attempt", "observation", "test_result", "commit",
    "failure", "fix", "decision", "user_feedback",
}
_PAYLOAD_FIELDS = {
    "situation", "goal", "approach", "action", "observed_result", "lesson",
    "applicability", "attempt_state", "resolution_state",
    "attribution_limits", "exposed_refs", "procedure_refs", "skill_refs",
}
_REQUIRED_PAYLOAD_FIELDS = {
    "situation", "approach", "observed_result", "lesson", "applicability",
}
_LIST_PAYLOAD_FIELDS = {"exposed_refs", "procedure_refs", "skill_refs"}
_ATTEMPT_STATES = {"success", "failure", "partial", "mixed", "unknown"}
_RESOLUTION_STATES = {
    "not_applicable", "unresolved", "diagnosed", "fix_proposed",
    "fix_validated", "corrected_with_cost",
}
_SOURCE_RANGE_FIELDS = {
    "source_path", "start", "end", "chunk_id", "captured_at",
    "redaction_state",
}


def _required_text(value, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} must be non-empty")
    return cleaned


def _event_id(idempotency_key: str) -> str:
    digest = hashlib.sha256(
        f"experience-event-v{CAPTURE_SCHEMA_VERSION}\0{idempotency_key}".encode(
            "utf-8")).hexdigest()
    return "experience-event-" + digest[:24]


def _experience_id(session_id: str, task_id: str) -> str:
    digest = hashlib.sha256(f"{session_id}\0{task_id}".encode("utf-8")).hexdigest()
    return "experience-" + digest[:20]


def _validated_payload(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError("payload must be an object")
    unknown = sorted(set(value) - _PAYLOAD_FIELDS)
    if unknown:
        raise ValueError("payload contains forbidden fields: " + ", ".join(unknown))
    result = {}
    for field, raw in value.items():
        if field in _LIST_PAYLOAD_FIELDS:
            if not isinstance(raw, list) or any(
                    not isinstance(item, str) or not item.strip() for item in raw):
                raise ValueError(f"payload.{field} must be a list of non-empty strings")
            result[field] = [item.strip() for item in raw]
        else:
            result[field] = str(raw or "").strip()
    missing = sorted(field for field in _REQUIRED_PAYLOAD_FIELDS
                     if not result.get(field))
    if missing:
        raise ValueError("payload requires non-empty " + ", ".join(missing))
    attempt = result.get("attempt_state", "unknown")
    resolution = result.get("resolution_state", "not_applicable")
    if attempt not in _ATTEMPT_STATES:
        raise ValueError("invalid attempt_state")
    if resolution not in _RESOLUTION_STATES:
        raise ValueError("invalid resolution_state")
    result["attempt_state"] = attempt
    result["resolution_state"] = resolution
    return result


def _source_refs(vault: Path, ranges, *, observed_at: str) -> list[dict]:
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("source_ranges must contain at least one exact range")
    refs = []
    for index, item in enumerate(ranges):
        if not isinstance(item, dict):
            raise ValueError(f"source_ranges[{index}] must be an object")
        unknown = sorted(set(item) - _SOURCE_RANGE_FIELDS)
        if unknown:
            raise ValueError(
                f"source_ranges[{index}] contains unknown fields: " + ", ".join(unknown))
        refs.append(_source_ref.make_source_ref(
            vault, _required_text(item.get("source_path"), "source_path"),
            start=item.get("start"), end=item.get("end"),
            chunk_id=str(item.get("chunk_id") or ""),
            captured_at=str(item.get("captured_at") or observed_at),
            redaction_state=str(item.get("redaction_state") or "clear"),
        ))
    return refs


def capture_event(value: dict, *, vault: Path | None = None) -> dict:
    root = (Path(vault) if vault is not None else
            Path(_required_text(os.environ.get("KENNISBANK_VAULT"),
                                "KENNISBANK_VAULT"))).expanduser().resolve()
    if not _settings.get("experience_capture", False, vault=root):
        return {"status": "disabled", "created": False}
    if not isinstance(value, dict):
        raise ValueError("input must be an object")
    allowed = {
        "idempotency_key", "session_id", "task_id", "event_type",
        "observed_at", "payload", "source_ranges",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError("input contains unknown fields: " + ", ".join(unknown))
    key = _required_text(value.get("idempotency_key"), "idempotency_key")
    session_id = _required_text(value.get("session_id"), "session_id")
    task_id = _required_text(value.get("task_id"), "task_id")
    event_type = _required_text(value.get("event_type"), "event_type")
    observed_at = _required_text(value.get("observed_at"), "observed_at")
    if event_type not in _EVENT_TYPES:
        raise ValueError("invalid event_type")
    payload = _validated_payload(value.get("payload"))
    refs = _source_refs(root, value.get("source_ranges"), observed_at=observed_at)
    event_id = _event_id(key)

    conn = _experience.connect(_experience.ledger_path(root))
    try:
        _experience.ensure_ledger_schema(conn)
        created = _experience.append_event(
            conn, event_id=event_id, session_id=session_id, task_id=task_id,
            event_type=event_type, observed_at=observed_at, payload=payload,
            source_refs=refs, schema_version=CAPTURE_SCHEMA_VERSION)
    finally:
        conn.close()
    return {
        "status": "ok", "created": created, "event_id": event_id,
        "experience_id": _experience_id(session_id, task_id),
        "source_ref_count": len(refs), "projection_written": False,
    }


def main() -> int:
    try:
        value = json.loads(sys.stdin.read() or "{}")
        result = capture_event(value)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
