"""TASK-84: GET /graphify-html serves the graphify-out/graph.html page.

The Graphify lens embeds this page in an iframe; a missing file must be a
clean 404 (the lens shows a degraded message), never a 500 or empty 200.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app

HTML = "<!doctype html><html><body>graphify</body></html>"


def _client(vault: Path) -> TestClient:
    return TestClient(create_app(vault))


def test_graphify_html_served_with_content_type(vault_factory):
    vault = vault_factory()
    out = vault / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.html").write_text(HTML, encoding="utf-8")

    resp = _client(vault).get("/graphify-html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == HTML


def test_graphify_html_head_probe(vault_factory):
    # The lens probes with HEAD before embedding; @app.get alone would 405.
    vault = vault_factory()
    out = vault / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.html").write_text(HTML, encoding="utf-8")

    resp = _client(vault).head("/graphify-html")
    assert resp.status_code == 200


def test_graphify_html_missing_is_404(vault_factory):
    vault = vault_factory()
    assert _client(vault).get("/graphify-html").status_code == 404
