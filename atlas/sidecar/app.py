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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from atlas.sidecar import sources

VERSION = "0.1.0"

# The frontend is served cross-origin from the sidecar: a localhost dev port in
# dev, and the Tauri webview origin (tauri://localhost, https://tauri.localhost
# on Windows) when bundled. Allow those, reject everything else. Loopback-only
# binding remains the real trust boundary.
_CORS_ORIGIN_REGEX = (
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    r"tauri://localhost|https://tauri\.localhost)$"
)


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
    recall_fn: Callable[[str, int], dict] | None = None,
    links_fn: Callable[[], dict] | None = None,
) -> FastAPI:
    vault = Path(vault)
    app = FastAPI(title="KennisBank Atlas sidecar", version=VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_CORS_ORIGIN_REGEX,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def _recall(q: str, k: int) -> dict:
        fn = recall_fn or (lambda query, top_k: sources.recall_waterfall(vault, query, top_k))
        try:
            return fn(q, k)
        except Exception:
            # Fail-open: a recall failure (Ollama down, index missing) degrades
            # the lens rather than erroring the whole app.
            return {"status": "degraded", "query": q,
                    "stages": {"vector": [], "fts": [], "rrf": [], "rerank": []},
                    "final": []}

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
    def graph(include_memory: bool = False) -> dict:
        return sources.build_graph(vault, include_memory=include_memory)

    @app.get("/timeline")
    def timeline(bucket: str = "day",
                 frm: str | None = Query(default=None, alias="from"),
                 to: str | None = None, dimension: str = "event") -> dict:
        return sources.build_timeline(
            vault, bucket=bucket, frm=frm, to=to, dimension=dimension
        )

    @app.get("/memory-health")
    def memory_health() -> dict:
        return sources.build_memory_health(vault)

    @app.get("/provenance")
    def provenance() -> dict:
        return sources.build_provenance(vault)

    @app.get("/doc")
    def doc(path: str = "") -> dict:
        try:
            return sources.read_doc(vault, path)
        except sources.DocError as exc:
            raise HTTPException(status_code=exc.code, detail=exc.detail)

    @app.get("/asset")
    def asset(path: str = ""):
        try:
            target, media = sources.resolve_asset(vault, path)
        except sources.DocError as exc:
            raise HTTPException(status_code=exc.code, detail=exc.detail)
        return FileResponse(target, media_type=media)

    @app.get("/recall")
    def recall(q: str = "", k: int = 3) -> dict:
        return _recall(q, k)

    @app.get("/memory-links")
    def memory_links() -> dict:
        fn = links_fn or (lambda: sources.build_memory_links(vault))
        try:
            return fn()
        except Exception:
            return {"status": "degraded", "links": {}, "counts": {}, "types": {}}

    # Warm the memory-links cache in the background (~47s) so the overlay is
    # ready when the user opens it. Only when a real index exists (not in tests).
    if links_fn is None and (vault / ".claude" / "kb-index.db").exists():
        import threading

        threading.Thread(
            target=lambda: sources.build_memory_links(vault), daemon=True
        ).start()

    return app
