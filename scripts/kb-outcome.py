#!/usr/bin/env python3
"""Record conservative, local session outcome observations off the hot path."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience  # noqa: E402
import _outcome  # noqa: E402


def extract_observations(transcript_path: Path) -> dict:
    if not transcript_path or not transcript_path.is_file():
        return {}
    try:
        text = transcript_path.read_text(encoding="utf-8", errors="replace")[:20_000_000]
    except OSError:
        return {}
    lower = text.lower()
    tests = []
    if re.search(r"\b\d+\s+passed\b|tests?\s+(?:all\s+)?passed|pytest[^\n]*passed", lower):
        tests.append("passed")
    if re.search(r"\b\d+\s+failed\b|tests?\s+failed|pytest[^\n]*failed|traceback", lower):
        tests.append("failed")
    commit = ""
    match = re.search(r"\bcommit(?:ted)?\b[^0-9a-f]{0,20}([0-9a-f]{7,40})\b", lower)
    if match:
        commit = match.group(1)
    return {"tests": tests, "commit": commit,
            "reverted": bool(re.search(r"\brevert(?:ed|ing)?\b", lower))}


def record_session_outcome(payload: dict, *, vault: Path | None = None) -> dict:
    payload = dict(payload or {})
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return {"created": False, "state": "unknown", "evidence": []}
    root = Path(vault) if vault is not None else Path(
        os.environ.get("KENNISBANK_VAULT", "."))
    task_id = str(payload.get("task_id") or "session")
    observations = extract_observations(Path(str(payload.get("transcript_path") or "")))
    derived = _outcome.derive_outcome(observations)
    key = f"{session_id}|{task_id}".encode("utf-8")
    outcome_id = "session-outcome:" + hashlib.sha256(key).hexdigest()[:24]
    conn = _experience.connect(root / ".claude" / "kb-experience.db")
    try:
        _experience.ensure_schema(conn)
        created = _experience.record_outcome(
            conn, outcome_id=outcome_id, session_id=session_id, task_id=task_id,
            state=derived["state"], evidence=derived["evidence"],
            attribution_strength=derived["attribution_strength"])
    finally:
        conn.close()
    return {"created": created, "outcome_id": outcome_id,
            "state": derived["state"], "evidence": derived["evidence"]}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        record_session_outcome(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
