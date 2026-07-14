"""TASK-27.3: the frontend reaches the sidecar cross-origin (dev server on a
different localhost port, and the Tauri webview origin), so the sidecar must
emit CORS headers for loopback/tauri origins while rejecting foreign origins."""
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.sidecar.app import create_app


def test_cors_allows_localhost_dev_origin(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.get("/health", headers={"Origin": "http://localhost:5177"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5177"


def test_cors_allows_tauri_origin(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.get("/health", headers={"Origin": "https://tauri.localhost"})
    assert resp.headers.get("access-control-allow-origin") == "https://tauri.localhost"


def test_cors_allows_windows_tauri_http_origin(tmp_path: Path):
    # Tauri v2 on Windows serves the webview from http://tauri.localhost (no
    # TLS); without this origin every fetch in the bundled app fails.
    client = TestClient(create_app(tmp_path))
    resp = client.get("/health", headers={"Origin": "http://tauri.localhost"})
    assert resp.headers.get("access-control-allow-origin") == "http://tauri.localhost"


def test_cors_rejects_foreign_origin(tmp_path: Path):
    client = TestClient(create_app(tmp_path))
    resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in resp.headers
