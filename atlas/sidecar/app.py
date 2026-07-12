"""KennisBank Atlas sidecar (TASK-27.2).

A localhost-only FastAPI app that reads the local KennisBank stores and serves
one JSON payload per Atlas lens. Read-only, fail-open, no outbound network
except local Ollama for the live recall waterfall.

The app is built via ``create_app(vault)`` so the vault root is injected. The
runtime entrypoint resolves it through ``vault_root()`` (ADR-0002); tests inject
a fixture vault. Never hardcode a vault path here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import FastAPI

from atlas.sidecar import sources

VERSION = "0.1.0"


def _default_ollama_probe() -> bool:
    """Best-effort liveness check against the local Ollama HTTP API."""
    try:
        import httpx

        resp = httpx.get("http://127.0.0.1:11434/api/version", timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


def _source_readiness(vault: Path, ollama_probe: Callable[[], bool]) -> dict[str, bool]:
    claude = vault / ".claude"
    return {
        "kb_index": (claude / "kb-index.db").exists(),
        "activity": (claude / "kb-activity.db").exists(),
        "usage": (claude / "kb-usage.db").exists(),
        "memory": (vault / "09-memory").is_dir(),
        "graph": (vault / "graphify-out" / "graph.json").exists(),
        "ollama": bool(ollama_probe()),
    }


def _overall_status(sources: dict[str, bool]) -> str:
    values = sources.values()
    if all(values):
        return "ok"
    if not any(values):
        return "empty"
    return "degraded"


def create_app(
    vault: Path,
    *,
    ollama_probe: Callable[[], bool] = _default_ollama_probe,
) -> FastAPI:
    vault = Path(vault)
    app = FastAPI(title="KennisBank Atlas sidecar", version=VERSION)

    @app.get("/health")
    def health() -> dict:
        sources = _source_readiness(vault, ollama_probe)
        return {
            "status": _overall_status(sources),
            "version": VERSION,
            "vault": str(vault),
            "sources": sources,
        }

    @app.get("/graph")
    def graph() -> dict:
        return sources.build_graph(vault)

    return app
