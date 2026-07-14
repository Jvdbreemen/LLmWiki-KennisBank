"""TASK-27.4/27.3 inspect: GET /doc?path= returns a vault file for reading.

Read-only and path-traversal-guarded (fail-closed): the resolved path must stay
inside the vault and be a .md file, otherwise 400/404 with no content leak.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def _doc(vault: Path, path: str):
    return TestClient(create_app(vault)).get("/doc", params={"path": path})


def test_doc_returns_markdown_content(vault_factory):
    vault = vault_factory(wiki=[{"stem": "alpha", "body": "# Alpha\n\nHallo wereld."}])
    resp = _doc(vault, "02-wiki/alpha.md")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["path"] == "02-wiki/alpha.md"
    assert "Hallo wereld." in body["content"]


def test_doc_rejects_path_traversal(vault_factory):
    vault = vault_factory(wiki=[{"stem": "alpha", "body": "x"}])
    (vault.parent / "secret.md").write_text("TOP SECRET", encoding="utf-8")
    resp = _doc(vault, "../secret.md")
    assert resp.status_code in (400, 404)
    assert "TOP SECRET" not in resp.text


def test_doc_rejects_non_markdown(vault_factory):
    vault = vault_factory(wiki=[{"stem": "alpha", "body": "x"}])
    (vault / ".claude").mkdir(parents=True, exist_ok=True)
    (vault / ".claude" / "kb-index.db").write_bytes(b"binary")
    resp = _doc(vault, ".claude/kb-index.db")
    assert resp.status_code == 400


def test_doc_missing_file_404(vault_factory):
    vault = vault_factory(wiki=[{"stem": "alpha", "body": "x"}])
    assert _doc(vault, "02-wiki/nope.md").status_code == 404
