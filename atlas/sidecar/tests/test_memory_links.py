"""TASK-27.14 sidecar: /memory-links.

Links each memory fragment to its nearest wiki article (hybrid vector+FTS on the
stored index, no re-embed, no rerank). The endpoint is injectable so the shape
is tested hermetically; without an index it fails open to empty.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def test_memory_links_fail_open_without_index(tmp_path: Path):
    body = TestClient(create_app(tmp_path)).get("/memory-links").json()
    assert body["status"] == "empty"
    assert body["links"] == {}
    assert body["counts"] == {}


def test_memory_links_shape_via_injection(tmp_path: Path):
    def fake() -> dict:
        return {
            "status": "ok",
            "links": {"m-1": "02-wiki/alpha.md", "m-2": "02-wiki/alpha.md",
                      "m-3": "02-wiki/beta.md"},
            "counts": {"02-wiki/alpha.md": 2, "02-wiki/beta.md": 1},
        }

    body = TestClient(create_app(tmp_path, links_fn=fake)).get("/memory-links").json()
    assert body["counts"]["02-wiki/alpha.md"] == 2
    # counts are consistent with links (each link increments its target)
    from collections import Counter
    assert dict(Counter(body["links"].values())) == body["counts"]
