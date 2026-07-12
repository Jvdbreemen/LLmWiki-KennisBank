"""TASK-27.2 sidecar: /health liveness and source readiness.

Contract (ADR-0004): GET /health returns a top-level status in
{ok, degraded, empty}, the resolved vault path, a version string, and a
`sources` map reporting readiness of each local store.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _client(vault: Path, ollama: bool = False) -> TestClient:
    # ollama readiness is injected so tests stay hermetic regardless of whether
    # a real Ollama server happens to be running on the build machine.
    return TestClient(create_app(vault, ollama_probe=lambda: ollama))


def test_health_reports_status_and_sources(tmp_path: Path):
    resp = _client(tmp_path).get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded", "empty"}
    assert body["vault"] == str(tmp_path)
    assert isinstance(body["version"], str) and body["version"]
    assert set(body["sources"]) == {
        "kb_index",
        "activity",
        "usage",
        "memory",
        "graph",
        "ollama",
    }
    # An empty fixture vault has no stores, so every source is unready.
    assert all(v is False for v in body["sources"].values())


def test_health_flags_present_graph_store(tmp_path: Path):
    graph = tmp_path / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text('{"nodes": [], "links": []}', encoding="utf-8")

    body = _client(tmp_path).get("/health").json()

    assert body["sources"]["graph"] is True
