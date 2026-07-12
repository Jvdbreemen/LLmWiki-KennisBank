"""TASK-27.2 sidecar: /timeline.

Contract (ADR-0004): server-side aggregation of activity_events into day/week
buckets. Bi-temporal: each bucket reports both event_count (by event_time) and
capture_count (by captured_at), plus by_kind for the event dimension. Serves
the Timeline lens (27.7): event-time vs capture-time.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _timeline(vault: Path, **params) -> dict:
    return TestClient(create_app(vault)).get("/timeline", params=params).json()


def test_timeline_day_buckets_counts_and_kinds(vault_factory):
    events = [
        {"id": "1", "event_time": "2026-07-01T09:00:00+02:00",
         "captured_at": "2026-07-01T09:00:00+02:00", "activity_kind": "edit"},
        {"id": "2", "event_time": "2026-07-01T15:00:00+02:00",
         "captured_at": "2026-07-02T08:00:00+02:00", "activity_kind": "recall"},
        {"id": "3", "event_time": "2026-07-02T10:00:00+02:00",
         "captured_at": "2026-07-02T10:00:00+02:00", "activity_kind": "edit"},
    ]
    body = _timeline(vault_factory(events=events), bucket="day")

    assert body["status"] == "ok"
    buckets = {b["start"][:10]: b for b in body["buckets"]}

    # 2026-07-01: two events (edit, recall); one captured that day (event 1)
    assert buckets["2026-07-01"]["event_count"] == 2
    assert buckets["2026-07-01"]["capture_count"] == 1
    assert buckets["2026-07-01"]["by_kind"] == {"edit": 1, "recall": 1}

    # 2026-07-02: one event (edit); two captured that day (events 2 and 3)
    assert buckets["2026-07-02"]["event_count"] == 1
    assert buckets["2026-07-02"]["capture_count"] == 2
    assert buckets["2026-07-02"]["by_kind"] == {"edit": 1}

    # buckets are chronologically ordered
    starts = [b["start"] for b in body["buckets"]]
    assert starts == sorted(starts)


def test_timeline_fail_open_without_db(tmp_path: Path):
    body = _timeline(tmp_path, bucket="day")
    assert body["status"] == "empty"
    assert body["buckets"] == []
