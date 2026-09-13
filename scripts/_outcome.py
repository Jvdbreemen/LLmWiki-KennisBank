#!/usr/bin/env python3
"""Derive conservative outcome labels from local, observable evidence."""
from __future__ import annotations


def derive_outcome(observations: dict | None) -> dict:
    observations = dict(observations or {})
    evidence = []
    tests = [str(value).lower() for value in (observations.get("tests") or [])]
    passed = any(value in {"passed", "pass", "green", "success"} for value in tests)
    failed = any(value in {"failed", "fail", "red", "error"} for value in tests)
    if passed:
        evidence.append("tests:passed")
    if failed:
        evidence.append("tests:failed")
    if observations.get("commit"):
        evidence.append("commit:" + str(observations["commit"]))
    if observations.get("reverted"):
        evidence.append("reverted:true")
        failed = True
    feedback = str(observations.get("user_feedback") or "").strip()
    if feedback:
        evidence.append("user_feedback")
    if failed and passed:
        state = "mixed"
    elif failed:
        state = "failure"
    elif passed and observations.get("commit"):
        state = "success"
    elif passed:
        state = "success"
    else:
        state = "unknown"
    attribution = "none"
    if feedback:
        lower = feedback.lower()
        attribution = "explicit" if any(word in lower for word in
                                         ("helped", "helpful", "solved", "worked")) else "weak"
    return {"state": state, "evidence": evidence,
            "attribution_strength": attribution,
            "feedback": feedback}
