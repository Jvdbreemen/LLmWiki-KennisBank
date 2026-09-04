#!/usr/bin/env python3
"""Deterministic event-to-experience projection; no unsupported LLM claims."""
from __future__ import annotations

import json
import hashlib
from collections import defaultdict

import _experience


def _events(conn, session_id: str, task_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT payload_json, source_refs_json FROM experience_events "
        "WHERE session_id=? AND task_id=? ORDER BY observed_at, event_id",
        (session_id, task_id)).fetchall()
    result = []
    for payload, refs in rows:
        try:
            decoded_payload = json.loads(payload or "{}")
            decoded_refs = json.loads(refs or "[]")
        except (TypeError, ValueError):
            # Keep the append-only event untouched; an unreadable derived
            # proposition must not block the rest of the session projection.
            continue
        if not isinstance(decoded_payload, dict) or not isinstance(decoded_refs, list):
            continue
        result.append({"payload": decoded_payload, "source_refs": decoded_refs})
    return result


def derive_experience_values(conn, session_id: str, task_id: str,
                             experience_id: str) -> dict:
    """Derive values from a canonical ledger without writing a projection."""
    events = _events(conn, session_id, task_id)
    outcomes = conn.execute(
        "SELECT outcome_id, state, evidence_json FROM experience_outcomes "
        "WHERE session_id=? AND task_id=? "
        "ORDER BY observed_at, outcome_id", (session_id, task_id)).fetchall()
    payloads = [event["payload"] for event in events]
    refs = []
    exposed_refs, procedure_refs, skill_refs = [], [], []
    for event in events:
        refs.extend(event["source_refs"])
        for key, target in (("exposed_refs", exposed_refs),
                            ("procedure_refs", procedure_refs),
                            ("skill_refs", skill_refs)):
            value = event["payload"].get(key) or []
            target.extend(value if isinstance(value, list) else [value])
    latest = {}
    for payload in payloads:
        latest.update({key: str(value) for key, value in payload.items()
                       if value is not None and key in {
                           "situation", "goal", "approach", "action",
                           "observed_result", "lesson", "applicability"}})
    outcome_id = outcomes[-1][0] if outcomes else ""
    outcome_states = {row[1] for row in outcomes}
    outcome_state = ("mixed" if {"success", "failure"} <= outcome_states
                     else outcomes[-1][1] if outcomes else "unknown")
    conflicting = {"success", "failure"} <= outcome_states
    outcome_refs = [row[0] for row in outcomes]
    status = "validated" if refs and outcome_id and outcome_state != "unknown" else "candidate"
    if conflicting:
        status = "candidate"
    values = {
        "experience_id": experience_id, "session_id": session_id, "task_id": task_id,
        "status": status, "situation": latest.get("situation", ""),
        "goal": latest.get("goal", ""), "approach": latest.get("approach", ""),
        "action": latest.get("action", ""), "observed_result": latest.get("observed_result", ""),
        "lesson": latest.get("lesson", ""), "applicability": latest.get("applicability", ""),
        "outcome_state": outcome_state, "confidence": 0.8 if status == "validated" else 0.2,
        "source_refs": refs, "outcome_refs": outcome_refs,
        "exposed_refs": exposed_refs, "procedure_refs": procedure_refs,
        "skill_refs": skill_refs,
    }
    return values


def derive_experience(conn, session_id: str, task_id: str, experience_id: str) -> dict:
    values = derive_experience_values(conn, session_id, task_id, experience_id)
    try:
        created = _experience.save_experience(conn, **values)
    except ValueError:
        # Contradictory or incomplete evidence remains a candidate rather than
        # being forced through the validation gate.
        values["status"] = "candidate"
        values["confidence"] = 0.2
        created = _experience.save_experience(conn, **values)
    result = _experience.experience(conn, experience_id)
    result["created"] = created
    return result


def dead_end_survival_report(events, records, *, preserve_threshold: float = 0.8) -> dict:
    """Measure whether failure events survive as evidence-bound lessons."""
    failures = [event for event in (events or [])
                if str(event.get("event_type") or "").lower() == "failure"
                or bool((event.get("payload") or {}).get("dead_end"))]
    retained_refs = set()
    retained = [record for record in (records or [])
                if str(record.get("lesson") or "").strip()]
    for record in retained:
        retained_refs.update(str(ref) for ref in (record.get("source_refs") or []))
    survived = sum(bool(set(map(str, event.get("source_refs") or [])) & retained_refs)
                   for event in failures)
    total = len(failures)
    rate = survived / total if total else None
    decision = ("insufficient_evidence" if total == 0 else
                "preserve" if rate >= preserve_threshold else "review")
    return {"dead_end_events": total, "survived_events": survived,
            "lost_events": total - survived, "survival_rate": rate,
            "preserve_threshold": preserve_threshold, "decision": decision}


def consolidation_report(records, *, min_support: int = 2,
                         extractor_version: str = "1") -> dict:
    """Create deterministic, reversible consolidation proposals only."""
    if min_support < 2:
        raise ValueError("min_support must be at least 2")
    groups = defaultdict(list)
    for record in records or []:
        lesson = str(record.get("lesson") or "").strip()
        scope = str(record.get("applicability") or "").strip()
        if lesson and scope:
            groups[(lesson, scope)].append(record)
    proposals = []
    for (lesson, scope), group in sorted(groups.items()):
        valid = [record for record in group
                 if record.get("status") == "validated"
                 and record.get("source_refs") and record.get("outcome_refs")]
        states = {str(record.get("outcome_state") or "unknown") for record in valid}
        if len(valid) < min_support or len(states) != 1:
            continue
        evidence_key = "|".join((lesson, scope, *sorted(
            str(record.get("experience_id") or "") for record in valid)))
        proposal_id = "consolidation-" + hashlib.sha256(
            evidence_key.encode("utf-8")).hexdigest()[:16]
        proposals.append({
            "proposal_id": proposal_id, "lesson": lesson, "applicability": scope,
            "support": len(valid), "outcome_state": next(iter(states)),
            "experience_ids": sorted(str(record["experience_id"]) for record in valid),
            "source_refs": sorted({str(ref) for record in valid
                                    for ref in record["source_refs"]}),
            "outcome_refs": sorted({str(ref) for record in valid
                                     for ref in record["outcome_refs"]}),
            "extractor_version": extractor_version, "reversible": True,
        })
    return {"proposals": proposals, "mutated": False,
            "reversible": True, "min_support": min_support,
            "extractor_version": extractor_version}
