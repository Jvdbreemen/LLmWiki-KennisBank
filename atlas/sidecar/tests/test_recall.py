"""TASK-27.2 sidecar: /recall.

Contract (ADR-0004): the live query waterfall. Reuses kb-recall so `final`
ordering matches exactly (AC#2). The recall function is injected so the endpoint
is tested hermetically without Ollama; a separate live smoke proves real parity.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def test_recall_passes_query_and_preserves_final_order(tmp_path: Path):
    captured = {}

    def fake_recall(q: str, k: int) -> dict:
        captured["q"], captured["k"] = q, k
        return {
            "status": "ok",
            "query": q,
            "stages": {"vector": [], "fts": [], "rrf": [], "rerank": []},
            "final": [
                {"path": "09-memory/a.md", "score": 0.9, "snippet": "a"},
                {"path": "09-memory/b.md", "score": 0.5, "snippet": "b"},
            ],
        }

    app = create_app(tmp_path, recall_fn=fake_recall)
    body = TestClient(app).get("/recall", params={"q": "otgw", "k": 2}).json()

    assert captured == {"q": "otgw", "k": 2}
    assert body["query"] == "otgw"
    assert [h["path"] for h in body["final"]] == ["09-memory/a.md", "09-memory/b.md"]
    assert set(body["stages"]) == {"vector", "fts", "rrf", "rerank"}


def test_recall_fail_open_on_recall_error(tmp_path: Path):
    def boom(q: str, k: int) -> dict:
        raise RuntimeError("ollama down")

    app = create_app(tmp_path, recall_fn=boom)
    body = TestClient(app).get("/recall", params={"q": "x"}).json()

    assert body["status"] in {"degraded", "empty"}
    assert body["final"] == []
