"""TASK-91 F1/F2: heatmap + freshness in /overview en de /titles-index.

Alles pure GET (read-only invariant) en geaggregeerd in SQL — geen per-doc
reads op render-tijd (llm_wiki #604-les).
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _client(vault: Path) -> TestClient:
    return TestClient(create_app(vault))


def test_overview_heatmap_counts_events_per_day(vault_factory):
    today = date.today()
    d1 = today.isoformat()
    d2 = (today - timedelta(days=3)).isoformat()
    vault = vault_factory(events=[
        {"id": "e1", "event_time": f"{d1}T10:00:00", "captured_at": f"{d1}T10:00:00",
         "activity_kind": "edit"},
        {"id": "e2", "event_time": f"{d1}T11:00:00", "captured_at": f"{d1}T11:00:00",
         "activity_kind": "edit"},
        {"id": "e3", "event_time": f"{d2}T09:00:00", "captured_at": f"{d2}T09:00:00",
         "activity_kind": "edit"},
    ])
    r = _client(vault).get("/overview")
    assert r.status_code == 200
    hm = {b["day"]: b["n"] for b in r.json()["heatmap"]}
    assert hm[d1] == 2
    assert hm[d2] == 1


def test_overview_heatmap_failopen_without_activity_db(vault_factory):
    vault = vault_factory(memories=[])
    r = _client(vault).get("/overview")
    assert r.status_code == 200
    assert r.json()["heatmap"] == []


def test_overview_freshness_buckets(vault_factory):
    vault = vault_factory(memories=[])
    wdir = vault / "02-wiki"
    wdir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    fresh = today.isoformat()
    old = (today - timedelta(days=200)).isoformat()
    (wdir / "vers.md").write_text(
        f"---\ntitle: Vers\nstatus: actief\nupdated: {fresh}\n---\nx\n", encoding="utf-8")
    (wdir / "oud.md").write_text(
        f"---\ntitle: Oud\nstatus: actief\nupdated: {old}\n---\nx\n", encoding="utf-8")
    (wdir / "zonder.md").write_text(
        "---\ntitle: Zonder\nstatus: actief\n---\nx\n", encoding="utf-8")
    fr = _client(vault).get("/overview").json()["freshness"]
    assert fr["d7"] == 1
    assert fr["older"] == 1
    assert fr["unknown"] == 1


def test_titles_index_from_kbindex(vault_factory):
    vault = vault_factory(docs=[
        {"path": "/abs/vault/02-wiki/traefik.md", "layer": "wiki",
         "status": "current", "title": "Traefik"},
        {"path": "/abs/vault/09-memory/m1.md", "layer": "memory",
         "status": "current", "title": "M1"},
    ])
    r = _client(vault).get("/titles")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    titles = {i["title"]: i for i in body["items"]}
    assert set(titles) == {"Traefik", "M1"}
    assert titles["Traefik"]["layer"] == "wiki"


def test_titles_failopen_without_index(vault_factory):
    vault = vault_factory(memories=[])
    r = _client(vault).get("/titles")
    assert r.status_code == 200
    assert r.json() == {"status": "empty", "items": []}
