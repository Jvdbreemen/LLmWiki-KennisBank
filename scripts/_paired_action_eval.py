#!/usr/bin/env python3
"""Pure helpers for blinded baseline-versus-experience action review."""
from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _layer_eval


VERDICTS = ("a_only", "b_only", "both", "neither")
ARMS = ("baseline", "experience")


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def assignment_map(case_ids, *, seed: int = 224) -> dict[str, str]:
    """Return a deterministic, globally balanced mapping for which arm is A."""
    ids = [str(value) for value in case_ids]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("case ids must be non-empty and unique")
    ranked = sorted(ids, key=lambda value: (_sha256(f"{seed}:{value}"), value))
    baseline_a = set(ranked[:len(ranked) // 2])
    return {
        case_id: ("baseline" if case_id in baseline_a else "experience")
        for case_id in sorted(ids)
    }


def make_pair(*, case: dict, baseline: str, experience: str, a_arm: str,
              common_context_sha256: str, experience_ids, model: str):
    """Build a content-bearing blind packet plus a separate hidden arm key."""
    case_id = str(case.get("id") or "")
    query = str(case.get("query") or "").strip()
    baseline = str(baseline or "").strip()
    experience = str(experience or "").strip()
    if not case_id or not query or not baseline or not experience:
        raise ValueError("pair requires id, query, and two non-empty actions")
    if a_arm not in ARMS:
        raise ValueError("a_arm must be baseline or experience")
    record = dict((case.get("records") or [{}])[0])
    reference = {
        "observed_result": str(record.get("observed_result") or "").strip(),
        "lesson": str(record.get("lesson") or "").strip(),
        "applicability": str(record.get("applicability") or "").strip(),
        "source_refs": list(record.get("source_refs") or []),
    }
    options = {"baseline": baseline, "experience": experience}
    b_arm = "experience" if a_arm == "baseline" else "baseline"
    option_a = options[a_arm]
    option_b = options[b_arm]
    blind = {
        "schema_version": 1,
        "id": case_id,
        "query": query,
        "reference": reference,
        "option_a": option_a,
        "option_b": option_b,
    }
    key = {
        "schema_version": 1,
        "id": case_id,
        "a_arm": a_arm,
        "b_arm": b_arm,
        "option_a_sha256": _sha256(option_a),
        "option_b_sha256": _sha256(option_b),
        "query_sha256": _sha256(query),
        "common_context_sha256": str(common_context_sha256),
        "experience_ids": [str(value) for value in experience_ids],
        "model": str(model),
    }
    return blind, key


def verify_pair(blind: dict, key: dict) -> None:
    if str(blind.get("id") or "") != str(key.get("id") or ""):
        raise ValueError("pair and key ids differ")
    if key.get("a_arm") not in ARMS or key.get("b_arm") not in ARMS:
        raise ValueError("invalid hidden arm")
    if key.get("a_arm") == key.get("b_arm"):
        raise ValueError("hidden arms must differ")
    if _sha256(str(blind.get("query") or "")) != key.get("query_sha256"):
        raise ValueError("query hash mismatch")
    for label in ("a", "b"):
        observed = _sha256(str(blind.get(f"option_{label}") or ""))
        if observed != key.get(f"option_{label}_sha256"):
            raise ValueError(f"option {label.upper()} hash mismatch")


def _unique(rows, *, name: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        case_id = str(row.get("id") or "")
        if not case_id or case_id in result:
            raise ValueError(f"{name} require non-empty unique ids")
        result[case_id] = dict(row)
    return result


def score(pairs, keys, reviews, *, bootstrap: int = 10000,
          seed: int = 224) -> dict:
    """Unblind completed four-way judgments and return aggregate paired value."""
    pair_by_id = _unique(pairs, name="pairs")
    key_by_id = _unique(keys, name="keys")
    review_by_id = _unique(reviews, name="reviews")
    if set(pair_by_id) != set(key_by_id) or set(pair_by_id) != set(review_by_id):
        raise ValueError("pairs, keys, and reviews must contain identical ids")

    baseline_correct = []
    experience_correct = []
    verdicts = Counter()
    a_arms = Counter()
    for case_id in sorted(pair_by_id):
        blind = pair_by_id[case_id]
        key = key_by_id[case_id]
        review = review_by_id[case_id]
        verify_pair(blind, key)
        verdict = str(review.get("verdict") or "")
        if verdict not in VERDICTS:
            raise ValueError(f"invalid verdict for {case_id}: {verdict}")
        verdicts[verdict] += 1
        a_arms[str(key["a_arm"])] += 1
        a_correct = verdict in {"a_only", "both"}
        b_correct = verdict in {"b_only", "both"}
        arm_correct = {
            str(key["a_arm"]): a_correct,
            str(key["b_arm"]): b_correct,
        }
        baseline_correct.append(arm_correct["baseline"])
        experience_correct.append(arm_correct["experience"])

    result = _layer_eval.paired_binary_delta(
        baseline_correct, experience_correct, bootstrap=bootstrap, seed=seed)
    result["experience_correct"] = result.pop("experiment_correct")
    result["verdicts"] = {name: verdicts[name] for name in VERDICTS}
    result["a_arm_balance"] = {name: a_arms[name] for name in ARMS}
    result["value_gate"] = {
        "minimum_pairs": result["n"] >= 60,
        "delta_at_least_0_10": result["delta"] >= 0.10 - 1e-12,
    }
    result["value_gate"]["passes"] = all(result["value_gate"].values())
    return result
