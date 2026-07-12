"""TASK-27.4 inspect: GET /asset?path= serves a vault image for the viewer.

Read-only, path-traversal-guarded, and restricted to image extensions
(fail-closed): anything else is rejected with no bytes leaked.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app

# 1x1 transparent PNG.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


def _client(vault: Path) -> TestClient:
    return TestClient(create_app(vault))


def test_asset_serves_image_with_content_type(vault_factory):
    vault = vault_factory()
    media = vault / "07-media"
    media.mkdir(parents=True)
    (media / "pic.png").write_bytes(PNG)

    resp = _client(vault).get("/asset", params={"path": "07-media/pic.png"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content == PNG


def test_asset_rejects_traversal(vault_factory):
    vault = vault_factory()
    (vault.parent / "evil.png").write_bytes(PNG)
    assert _client(vault).get("/asset", params={"path": "../evil.png"}).status_code in (400, 404)


def test_asset_rejects_non_image(vault_factory):
    vault = vault_factory()
    (vault / "07-media").mkdir(parents=True)
    (vault / "07-media" / "note.md").write_text("secret", encoding="utf-8")
    assert _client(vault).get("/asset", params={"path": "07-media/note.md"}).status_code == 400
