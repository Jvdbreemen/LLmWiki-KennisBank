"""TASK-27.2 sidecar: /memory-health.

Contract (ADR-0004): counts by lifecycle bucket, supersede chains, warmth from
kb-usage, and the quarantine list. Serves the Memory Health lens (27.6).
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _mh(vault: Path) -> dict:
    return TestClient(create_app(vault)).get("/memory-health").json()


def test_memory_health_counts_chains_warmth_quarantine(vault_factory):
    memories = [
        {"stem": "m-active", "status": "current", "memory_type": "feit"},
        {"stem": "m-old", "status": "superseded", "superseded_by": ["m-new"]},
        {"stem": "m-new", "status": "current"},
        {"stem": "m-bad", "status": "quarantined", "quarantine_reason": "conflict"},
    ]
    usage = [
        {"stem": "m-active", "used": 5, "last_used": "2026-07-10"},
        {"stem": "m-new", "used": 2, "last_used": "2026-07-08"},
    ]
    body = _mh(vault_factory(memories=memories, usage=usage))

    assert body["status"] == "ok"
    assert body["counts"]["active"] == 2  # m-active + m-new
    assert body["counts"]["superseded"] == 1
    assert body["counts"]["quarantined"] == 1

    # supersede chain: m-old -> m-new
    chains = {tuple(c["chain"]) for c in body["supersede_chains"]}
    assert ("m-old", "m-new") in chains

    # warmth is joined from kb-usage, ordered warmest first
    warm = body["warmth"]
    assert [w["path"] for w in warm][:1] == ["m-active"]
    assert warm[0]["warmth"] >= warm[-1]["warmth"]

    # quarantine carries the reason
    q = {item["id"]: item["reason"] for item in body["quarantine"]}
    assert q == {"m-bad": "conflict"}


def test_memory_health_fail_open_without_memory_dir(tmp_path: Path):
    body = _mh(tmp_path)
    assert body["status"] == "empty"
    assert body["counts"]["active"] == 0
