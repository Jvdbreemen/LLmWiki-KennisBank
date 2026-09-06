"""Read-only diagnostics for the derived experience projection."""
from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath


def _source_path(ref) -> str:
    if isinstance(ref, dict):
        return str(ref.get("source_path") or "").strip().replace("\\", "/")
    return str(ref).split("#", 1)[0].strip().replace("\\", "/")


def lifecycle_report(records, *, existing_sources=(), redacted_sources=()) -> dict:
    """Report lifecycle and provenance hazards without changing records.

    ``existing_sources`` and ``redacted_sources`` are relative vault paths. A
    missing source is an orphan signal, not a reason to silently delete the
    experience: the append-only evidence may be recoverable from backup.
    """
    existing = {str(path).replace("\\", "/") for path in existing_sources or ()}
    redacted = {str(path).replace("\\", "/") for path in redacted_sources or ()}
    counts = Counter(str(record.get("status") or "unknown") for record in records or [])
    orphan, redacted_hits, unresolved, narrowed = [], [], [], []
    for record in records or []:
        eid = str(record.get("experience_id") or "")
        limits = str(record.get("attribution_limits") or "").lower()
        if record.get("narrowed") or "narrow" in limits:
            narrowed.append(eid)
        refs = [_source_path(ref) for ref in (record.get("source_refs") or [])]
        refs = [ref for ref in refs if ref]
        if not refs:
            unresolved.append(eid)
            continue
        if any(path in redacted for path in refs):
            redacted_hits.append(eid)
        if existing and any(path not in existing and path not in redacted for path in refs):
            orphan.append(eid)
    closed = [str(record.get("experience_id") or "") for record in (records or [])
              if str(record.get("status") or "") in {"retracted", "superseded"}]
    return {
        "records": sum(counts.values()),
        "status_counts": dict(sorted(counts.items())),
        "orphan_experiences": sorted(set(orphan)),
        "redacted_experiences": sorted(set(redacted_hits)),
        "unresolved_provenance": sorted(set(unresolved)),
        "retracted_or_superseded": sorted(set(closed)),
        "narrowed_experiences": sorted(set(narrowed)),
        "mutated": False,
    }
