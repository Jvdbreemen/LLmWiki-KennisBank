#!/usr/bin/env python3
"""Generate human-reviewable procedure proposals without mutating skills."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib


def proposal_report(records, *, min_support: int = 2, as_of: str | None = None,
                    max_age_days: int | None = None, allow_retracted: bool = False) -> dict:
    if min_support < 2:
        raise ValueError("min_support must be at least 2")
    as_of = as_of or date.today().isoformat()
    groups = defaultdict(list)
    for record in records or []:
        lesson = str(record.get("lesson") or "").strip()
        if lesson:
            groups[(lesson, str(record.get("applicability") or "").strip())].append(record)
    proposals, rejections = [], []
    for (lesson, scope), group in sorted(groups.items()):
        valid = []
        invalid_reasons = []
        for record in group:
            status = str(record.get("status") or "")
            if status == "retracted" and not allow_retracted:
                invalid_reasons.append("rejected/retracted experience")
                continue
            if status != "validated" and not (allow_retracted and status == "retracted"):
                invalid_reasons.append("rejected or unvalidated experience")
                continue
            if not record.get("source_refs") or not record.get("outcome_refs"):
                invalid_reasons.append("missing evidence links")
                continue
            if not str(record.get("action") or "").strip():
                invalid_reasons.append("missing concrete action")
                continue
            if str(record.get("valid_until") or "").strip() and str(record["valid_until"]) < as_of:
                invalid_reasons.append("expired validity")
                continue
            if max_age_days is not None:
                observed = str(record.get("observed_at") or record.get("created") or "")[:10]
                if not observed:
                    invalid_reasons.append("missing validity date")
                    continue
                try:
                    age = (date.fromisoformat(as_of) - date.fromisoformat(observed)).days
                except ValueError:
                    invalid_reasons.append("invalid validity date")
                    continue
                if age > max_age_days:
                    invalid_reasons.append("too old")
                    continue
            valid.append(record)
        states = {str(record.get("outcome_state") or "unknown") for record in valid}
        reason = ""
        if len(valid) < min_support:
            reason = invalid_reasons[0] if invalid_reasons else "insufficient repeated validated evidence"
        elif len(states) > 1:
            reason = "conflicting outcome states"
        if reason:
            rejections.append({"lesson": lesson, "scope": scope, "reason": reason,
                               "support": len(valid)})
            continue
        proposal_key = "|".join((lesson, scope, *sorted(
            str(record["experience_id"]) for record in valid)))
        proposal_id = "procedure-proposal-" + hashlib.sha256(
            proposal_key.encode("utf-8")).hexdigest()[:16]
        proposals.append({"proposal_id": proposal_id, "lesson": lesson, "scope": scope,
                          "support": len(valid), "actions": sorted({
                              str(record["action"]).strip() for record in valid}),
                          "outcome_quality": next(iter(states)),
                          "outcome_states": sorted(states),
                          "experience_ids": sorted(str(r["experience_id"]) for r in valid),
                          "source_refs": sorted({ref for r in valid for ref in r["source_refs"]}),
                          "outcome_refs": sorted({ref for r in valid for ref in r["outcome_refs"]})})
    return {"proposals": proposals, "rejections": rejections,
            "human_approval_required": True, "mutated": False,
            "thresholds": {"min_support": min_support, "as_of": as_of,
                           "max_age_days": max_age_days,
                           "allow_retracted": allow_retracted}}


def review_proposal(report: dict, proposal_id: str, decision: str) -> dict:
    """Record an owner decision without applying a procedure or skill change."""
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    proposal = next((item for item in report.get("proposals", [])
                     if item.get("proposal_id") == proposal_id), None)
    if proposal is None:
        raise KeyError(proposal_id)
    return {"proposal_id": proposal_id, "decision": decision,
            "approved": decision == "approve", "mutated": False,
            "human_approval_required": True}
