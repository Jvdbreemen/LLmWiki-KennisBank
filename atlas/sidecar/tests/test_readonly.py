"""TASK-27.2 DoD #4: the sidecar is read-only against source stores.

Hitting every data endpoint must not change any source DB. We assert on the
kb-activity.db hash before/after because every SQLite connection is opened with
?mode=ro, so a write is physically impossible.
"""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_endpoints_do_not_mutate_source_db(vault_factory):
    events = [
        {"id": "1", "event_time": "2026-07-01T09:00:00+02:00",
         "captured_at": "2026-07-01T09:00:00+02:00", "activity_kind": "edit"},
    ]
    vault = vault_factory(events=events)
    db = vault / ".claude" / "kb-activity.db"
    before = _digest(db)

    client = TestClient(create_app(vault))
    for path in ("/health", "/graph", "/timeline", "/memory-health", "/provenance"):
        assert client.get(path).status_code == 200

    assert _digest(db) == before
