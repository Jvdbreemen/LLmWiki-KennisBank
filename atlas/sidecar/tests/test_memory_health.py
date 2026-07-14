"""TASK-27.6 sidecar: /memory-health cockpit.

Counts, the unverified quarantine queue, supersede chains (with valid_until),
the importance x recency heatmap, and warmth/temperature. today is injected for
deterministic age/temperature assertions.
"""
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar import sources
from atlas.sidecar.app import create_app

# Reference "today" = the real current date, so the fixtures below stay valid
# whenever the suite runs and match a live KennisBank instance's clock. All
# fixture dates are expressed relative to it via `ago()`.
TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def _mh(vault: Path) -> dict:
    return TestClient(create_app(vault)).get("/memory-health").json()


def test_memory_health_endpoint_shape(vault_factory):
    memories = [
        {"stem": "m-active", "status": "current", "memory_type": "feit", "importance": 4},
        {"stem": "m-bad", "status": "quarantined", "quarantine_reason": "conflict"},
    ]
    body = _mh(vault_factory(memories=memories, usage=[]))
    assert body["status"] == "ok"
    assert set(body) >= {"counts", "queue", "supersede_chains", "heatmap", "warmth", "quarantine"}
    assert body["quarantine"] == [{"id": "m-bad", "reason": "conflict"}]


def test_queue_is_unverified_sorted_by_importance(vault_factory):
    memories = [
        {"stem": "u-lo", "status": "unverified", "importance": 2, "created": ago(11)},
        {"stem": "u-hi", "status": "unverified", "importance": 5, "created": ago(10)},
        {"stem": "verified", "status": "current", "importance": 5},
    ]
    r = sources.build_memory_health(vault_factory(memories=memories), today=TODAY)
    assert r["counts"]["unverified"] == 2
    assert [q["id"] for q in r["queue"]] == ["u-hi", "u-lo"]  # importance desc


def test_supersede_chain_carries_valid_until(vault_factory):
    memories = [
        {"stem": "old", "status": "superseded", "superseded_by": ["new"], "valid_until": ago(7)},
        {"stem": "new", "status": "current"},
    ]
    r = sources.build_memory_health(vault_factory(memories=memories), today=TODAY)
    chain = r["supersede_chains"][0]
    assert chain["chain"] == ["old", "new"]
    assert chain["valid_until"] == ago(7)


def test_heatmap_places_active_memory_by_importance_and_age(vault_factory):
    memories = [{"stem": "m", "status": "current", "importance": 4, "created": ago(10)}]
    r = sources.build_memory_health(vault_factory(memories=memories), today=TODAY)
    cell = r["heatmap"][0]
    assert cell == {"id": "m", "importance": 4, "age_days": 10}


def test_warmth_temperature_by_last_used(vault_factory):
    memories = [{"stem": a, "status": "current"} for a in ("hot", "warm", "cold")]
    usage = [
        {"stem": "hot", "used": 3, "last_used": ago(2)},    # <= 30d -> warm
        {"stem": "warm", "used": 2, "last_used": ago(60)},  # <= 90d -> tepid
        {"stem": "cold", "used": 1, "last_used": ago(120)},  # > 90d -> stale
    ]
    r = sources.build_memory_health(vault_factory(memories=memories, usage=usage), today=TODAY)
    # stems resolve to their real doc path (memory fixtures live in 09-memory/)
    temp = {w["path"]: w["temperature"] for w in r["warmth"]}
    assert temp == {"09-memory/hot.md": "warm", "09-memory/warm.md": "tepid",
                    "09-memory/cold.md": "stale"}


def test_memory_health_fail_open_without_memory_dir(tmp_path: Path):
    body = _mh(tmp_path)
    assert body["status"] == "empty"
    assert body["counts"]["active"] == 0
