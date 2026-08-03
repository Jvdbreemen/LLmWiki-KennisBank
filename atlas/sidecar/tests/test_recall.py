"""TASK-27.2 sidecar: /recall.

Contract (ADR-0004): the live query waterfall. Reuses kb-recall so `final`
ordering matches exactly (AC#2). The recall function is injected so the endpoint
is tested hermetically without Ollama; a separate live smoke proves real parity.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app
from atlas.sidecar import sources


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


def test_recall_waterfall_shape_and_factor_product(tmp_path: Path):
    # Contract the Recall Inspector relies on (AC#4): each rerank hit's factors
    # multiply to its final score, and all four stages are present.
    def wf(q: str, k: int) -> dict:
        return {
            "status": "ok", "query": q,
            "stages": {
                "vector": [{"path": "09-memory/a.md", "score": 1.0}],
                "fts": [{"path": "09-memory/a.md", "score": 0.5}],
                "rrf": [{"path": "09-memory/a.md", "score": 0.032}],
                "rerank": [{"path": "09-memory/a.md", "score": round(0.032 * 0.9 * 1.1 * 1.05 * 1.10, 6),
                            "factors": {"relevance": 0.032, "recency": 0.9,
                                        "importance": 1.1, "trust": 1.05,
                                        "usage": 1.10, "final": round(0.032 * 0.9 * 1.1 * 1.05 * 1.10, 6)}}],
            },
            "final": [{"path": "09-memory/a.md", "score": 0.036, "snippet": "a"}],
        }

    body = TestClient(create_app(tmp_path, recall_fn=wf)).get("/recall", params={"q": "x"}).json()
    assert set(body["stages"]) == {"vector", "fts", "rrf", "rerank"}
    hit = body["stages"]["rerank"][0]
    f = hit["factors"]
    product = f["relevance"] * f["recency"] * f["importance"] * f["trust"] * f["usage"]
    assert abs(product - f["final"]) < 1e-6
    assert abs(f["final"] - hit["score"]) < 1e-6


def test_recall_fail_open_on_recall_error(tmp_path: Path):
    def boom(q: str, k: int) -> dict:
        raise RuntimeError("ollama down")

    app = create_app(tmp_path, recall_fn=boom)
    body = TestClient(app).get("/recall", params={"q": "x"}).json()

    assert body["status"] in {"degraded", "empty"}
    assert body["final"] == []


class _FakeKbRecall:
    """Stands in for the vault-loaded kb-recall.py module. Deliberately has
    NO one_hop_neighbor attribute: if recall_waterfall's neighbour block ever
    calls that again instead of graph_neighbor, this raises AttributeError
    immediately instead of silently doing nothing (the bug the TASK-93 PR
    review caught: rank.one_hop_neighbor was deleted but a caller in this
    file still pointed at it, swallowed by a broad except)."""

    def __init__(self, neighbor):
        self._neighbor = neighbor

    def graph_neighbor(self, hits):
        return self._neighbor


class _FakeEmb:
    def doc_text(self, path, cap=200):
        return "neighbour snippet text"


def test_recall_neighbor_entry_uses_graph_neighbor(tmp_path: Path):
    npath = tmp_path / "02-wiki" / "neighbor.md"
    npath.parent.mkdir(parents=True)
    npath.write_text("inhoud", encoding="utf-8")
    hits = [{"path": str(tmp_path / "02-wiki" / "hit.md"), "layer": "wiki"}]

    entry = sources._recall_neighbor_entry(
        _FakeKbRecall({"path": str(npath), "stem": "neighbor"}), _FakeEmb(), hits, [])

    assert entry is not None
    assert entry["final"] == {"path": str(npath), "score": 0.0,
                              "snippet": "neighbour snippet text", "neighbor": True}
    assert entry["rerank"] == {"path": "02-wiki/neighbor.md", "score": 0.0,
                               "factors": {"final": 0.0}, "neighbor": True}


def test_recall_neighbor_entry_none_when_graph_has_no_neighbor(tmp_path: Path):
    assert sources._recall_neighbor_entry(_FakeKbRecall(None), _FakeEmb(), [], []) is None


def test_recall_neighbor_entry_skips_a_stem_already_in_final(tmp_path: Path):
    npath = tmp_path / "02-wiki" / "neighbor.md"
    npath.parent.mkdir(parents=True)
    npath.write_text("inhoud", encoding="utf-8")
    final = [{"path": str(npath)}]

    entry = sources._recall_neighbor_entry(
        _FakeKbRecall({"path": str(npath), "stem": "neighbor"}), _FakeEmb(), [], final)

    assert entry is None
