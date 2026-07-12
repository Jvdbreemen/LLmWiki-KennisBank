"""TASK-27.11 DoD #1: sidecar aggregation stays within a latency budget at scale.

Hermetic: synthesises a large activity store and asserts /timeline aggregation is
well under a second. Real-vault numbers (11198 events -> 0.76s; /graph 1106 raw
-> 95 nodes) are recorded in atlas/docs/perf-eval.md.
"""
import time
from datetime import date, timedelta

from atlas.sidecar import sources


def test_timeline_aggregation_under_budget(vault_factory):
    base = date(2026, 1, 1)
    events = []
    for i in range(4000):
        d = (base + timedelta(days=i % 180)).isoformat()
        events.append({
            "id": str(i),
            "event_time": f"{d}T09:00:00+02:00",
            "captured_at": f"{d}T09:00:00+02:00",
            "activity_kind": "edit" if i % 2 else "recall",
        })
    vault = vault_factory(events=events)

    t0 = time.perf_counter()
    r = sources.build_timeline(vault, bucket="week")
    dt = time.perf_counter() - t0

    assert r["status"] == "ok"
    total = sum(b["event_count"] for b in r["buckets"])
    assert total == 4000
    assert dt < 1.0, f"timeline aggregation too slow: {dt:.3f}s for 4000 events"
