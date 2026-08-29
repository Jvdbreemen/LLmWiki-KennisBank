#!/usr/bin/env python3
"""Explicit source-recall gateway; normal prompts never enter this route."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def label_hits(hits: list[dict], mode: str) -> list[dict]:
    """Expose source evidence with route and bounded confidence metadata."""
    labeled = []
    for hit in hits:
        item = dict(hit)
        item["retrieval_mode"] = mode
        item["confidence"] = {
            "cosine": hit.get("cos"),
            "lexical_match": bool(hit.get("fts")),
            "fresh": bool(hit.get("fresh")),
        }
        labeled.append(item)
    return labeled


def result_flags(hits: list[dict], mode: str, *, min_cos: float = 0.45) -> list[str]:
    """Represent absence and source-state caveats without hiding a hit."""
    flags = set()
    if not hits:
        flags.add("no_hit")
    for hit in hits:
        if hit.get("stale") or hit.get("fresh") is False:
            flags.add("stale")
        state = str(hit.get("status") or hit.get("source_state") or "").lower()
        if "supersed" in state or hit.get("superseded_by"):
            flags.add("superseded")
        if bool(hit.get("conflict")) or hit.get("conflict_group"):
            flags.add("conflict")
        cosine = hit.get("cos")
        if (not hit.get("fts") and cosine is not None
                and float(cosine) < float(min_cos)):
            flags.add("low_confidence")
    return sorted(flags)


def run(request: dict, *, embed_fn=None, vault: Path | None = None) -> dict:
    request = dict(request or {})
    mode = str(request.get("mode") or "normal").lower()
    if mode == "normal":
        return {"status": "not_routed", "hits": []}
    if mode not in {"explicit", "verify", "reconstruct", "fallback"}:
        return {"status": "not_routed", "hits": []}
    try:
        import _settings
        if not _settings.get("source_recall", False):
            return {"status": "disabled", "hits": []}
        import _source_recall as source
        import _embeddings as emb
        root = Path(vault) if vault is not None else Path(
            os.environ.get("KENNISBANK_VAULT", "."))
        db_path = root / ".claude" / "kb-source.db"
        if not db_path.is_file():
            return {"status": "unavailable", "hits": []}
        prompt = str(request.get("prompt") or "").strip()
        if not prompt:
            return {"status": "invalid", "hits": []}
        primary = request.get("primary_hits") or []
        if not source.should_route(mode, primary, float(request.get("floor", 0.5))):
            return {"status": "not_routed", "hits": []}
        embed = embed_fn or (lambda text: emb.embed_query(text))
        query_vector = embed(prompt)
        if query_vector is None:
            return {"status": "unavailable", "hits": []}
        conn = source.connect(db_path)
        try:
            hits = source.source_hits(
                conn, query_vector=query_vector, query_text=prompt,
                k=max(1, min(int(request.get("k", 5)), 20)),
                source_path=request.get("source_path"),
                embed_id=request.get("embed_id") or emb.embed_id(),
                source_root=root,
                min_cos=float(request.get("min_cos", 0.45)))
        finally:
            conn.close()
        hits = label_hits(hits, mode)
        try:
            import _usage
            _usage.log_exposures(
                [{"item_id": hit.get("source_path", "") + "#" + str(hit.get("chunk_index", "")),
                  "layer": "source", "rank": rank + 1, "source_id": hit.get("source_path", "")}
                 for rank, hit in enumerate(hits)],
                session_id=str(request.get("session_id") or ""),
                task_id=str(request.get("task_id") or ""), query=prompt,
                ts=str(request.get("timestamp") or ""), retrieval_kind=mode)
        except Exception:
            pass
        return {"status": "ok" if hits else "no_hit", "hits": hits,
                "mode": mode, "flags": result_flags(
                    hits, mode, min_cos=float(request.get("min_cos", 0.45)))}
    except Exception:
        return {"status": "unavailable", "hits": []}


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        print(json.dumps(run(request), ensure_ascii=False, sort_keys=True))
    except Exception:
        print(json.dumps({"status": "invalid", "hits": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
