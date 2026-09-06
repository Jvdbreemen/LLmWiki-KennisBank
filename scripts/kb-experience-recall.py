#!/usr/bin/env python3
"""Explicit gateway for reviewed experience lessons; never an automatic warning."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


_PUBLIC_FIELDS = {
    "experience_id", "task_id", "lesson", "applicability", "outcome_state",
    "attempt_state", "resolution_state", "confidence", "source_ref_ids",
    "outcome_refs", "score", "cos", "fts", "bm25", "retrieval_route",
    "validation_stamp",
}


def label_hits(hits: list[dict], mode: str, route: str | None = None) -> list[dict]:
    """Return the small public lesson contract without raw evidence content."""
    labeled = []
    for hit in hits:
        item = {key: value for key, value in hit.items() if key in _PUBLIC_FIELDS}
        item["recall_mode"] = mode
        item["evidence_kind"] = "validated_experience"
        item["retrieval_route"] = route or str(
            hit.get("retrieval_route") or "lexical_fallback")
        item["confidence_metadata"] = {
            "experience": hit.get("confidence"),
            "cosine": hit.get("cos"),
            "lexical_match": bool(hit.get("fts")),
            "evidence_bound": bool(
                hit.get("source_ref_ids") and hit.get("outcome_refs")),
        }
        labeled.append(item)
    return labeled


def _enabled(settings) -> bool:
    return bool(settings.get("experience_explicit_recall", False))


def _embedding(request: dict, embed_fn):
    """Return (vector, id), or (None, id) for an honest lexical fallback."""
    requested_id = str(request.get("embed_id") or "")
    try:
        if embed_fn is not None:
            return embed_fn(str(request["prompt"])), requested_id
        import _embeddings as emb
        return emb.embed_query(str(request["prompt"])), requested_id or emb.embed_id()
    except Exception:
        return None, requested_id


def _observe(route: str, status: str, hits: int, started: float) -> None:
    try:
        import _usage
        _usage.log_projection_metric(
            layer="experience", route=route, status=status, hits=hits,
            latency_ms=(time.perf_counter() - started) * 1000.0)
    except Exception:
        pass


def run(request: dict, *, embed_fn=None, vault: Path | None = None) -> dict:
    started = time.perf_counter()
    request = dict(request or {})
    mode = str(request.get("mode") or "normal").lower()
    if mode in {"failure", "advisory", "automatic", "fallback", "ranking",
                "promotion", "hook", "injection"}:
        return {"status": "policy_disabled", "hits": [], "mode": mode}
    if mode != "explicit":
        return {"status": "not_routed", "hits": []}
    try:
        import _settings
        if not _enabled(_settings):
            return {"status": "disabled", "hits": [], "mode": mode}
        import _experience as experience
        root = Path(vault) if vault is not None else Path(
            os.environ.get("KENNISBANK_VAULT", "."))
        db_path = experience.projection_path(root)
        if not db_path.is_file():
            return {"status": "unavailable", "hits": [], "mode": mode}
        prompt = str(request.get("prompt") or "").strip()
        if not prompt:
            return {"status": "invalid", "hits": [], "mode": mode}
        request["prompt"] = prompt
        query_vector, embed_id = _embedding(request, embed_fn)
        conn = experience.connect(db_path)
        route = "lexical_fallback"
        try:
            try:
                query_dim = len(query_vector) if query_vector is not None else 0
            except TypeError:
                query_dim = 0
            compatible = bool(
                query_dim > 0
                and embed_id
                and experience.vector_projection_compatible(
                    conn, embed_id=embed_id, query_dim=query_dim))
            if compatible:
                try:
                    experience.enable_recall_vectors(conn)
                    hits = experience.experience_hits(
                        conn, query_vector=query_vector, query_text=prompt,
                        k=min(max(int(request.get("k", 3)), 1), 3))
                    route = "hybrid"
                except Exception:
                    hits = experience.experience_lexical_hits(
                        conn, query_text=prompt,
                        k=min(max(int(request.get("k", 3)), 1), 3))
            else:
                hits = experience.experience_lexical_hits(
                    conn, query_text=prompt,
                    k=min(max(int(request.get("k", 3)), 1), 3))
        finally:
            conn.close()
        hits = label_hits(hits, mode, route)
        try:
            import _usage
            _usage.log_exposures(
                [{"item_id": hit.get("experience_id", ""), "layer": "experience",
                  "rank": rank + 1}
                 for rank, hit in enumerate(hits)],
                session_id=str(request.get("session_id") or ""),
                task_id=str(request.get("task_id") or ""), query="",
                ts=str(request.get("timestamp") or ""), retrieval_kind=mode)
        except Exception:
            pass
        result = {
            "status": "ok" if hits else "no_hit", "hits": hits,
            "mode": mode, "retrieval_route": route,
        }
        _observe(route, result["status"], len(hits), started)
        return result
    except Exception:
        return {"status": "unavailable", "hits": [], "mode": mode}


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        print(json.dumps(run(request), ensure_ascii=False, sort_keys=True))
    except Exception:
        print(json.dumps({"status": "invalid", "hits": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
