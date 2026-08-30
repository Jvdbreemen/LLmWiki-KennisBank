#!/usr/bin/env python3
"""Explicit gateway for validated experience recall and failure advisories."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def label_hits(hits: list[dict], mode: str) -> list[dict]:
    """Expose experience state and evidence strength without changing ranking."""
    labeled = []
    for hit in hits:
        item = dict(hit)
        item["recall_mode"] = mode
        item["evidence_kind"] = (
            "failure_advisory" if mode == "failure" else "validated_experience")
        item["confidence_metadata"] = {
            "experience": hit.get("confidence"),
            "cosine": hit.get("cos"),
            "lexical_match": bool(hit.get("fts")),
            "evidence_bound": bool(hit.get("source_refs") and hit.get("outcome_refs")),
        }
        labeled.append(item)
    return labeled


def failure_min_score(request: dict, experience) -> float:
    """Resolve an explicit override or the development-calibrated default."""
    if request.get("min_score") is not None:
        return float(request["min_score"])
    return float(experience.FAILURE_ADVISORY_MIN_COS)


def run(request: dict, *, embed_fn=None, vault: Path | None = None) -> dict:
    request = dict(request or {})
    mode = str(request.get("mode") or "normal").lower()
    if mode == "normal" or mode not in {"explicit", "failure"}:
        return {"status": "not_routed", "hits": []}
    try:
        import _settings
        if not _settings.get("experience_recall", False):
            return {"status": "disabled", "hits": []}
        import _experience as experience
        import _embeddings as emb
        root = Path(vault) if vault is not None else Path(
            os.environ.get("KENNISBANK_VAULT", "."))
        db_path = root / ".claude" / "kb-experience.db"
        if not db_path.is_file():
            return {"status": "unavailable", "hits": []}
        prompt = str(request.get("prompt") or "").strip()
        if not prompt:
            return {"status": "invalid", "hits": []}
        embed = embed_fn or (lambda text: emb.embed_query(text))
        query_vector = embed(prompt)
        if query_vector is None:
            return {"status": "unavailable", "hits": []}
        conn = experience.connect(db_path)
        try:
            experience.ensure_recall_schema(conn, dim=len(query_vector),
                                            embed_id=request.get("embed_id") or emb.embed_id())
            if mode == "failure":
                warning = experience.failure_advisory(
                    conn, query_vector=query_vector, query_text=prompt,
                    min_score=failure_min_score(request, experience))
                hits = [warning] if warning else []
            else:
                hits = experience.experience_hits(
                    conn, query_vector=query_vector, query_text=prompt,
                    k=max(1, min(int(request.get("k", 5)), 20)),
                    statuses=("validated",))
        finally:
            conn.close()
        hits = label_hits(hits, mode)
        try:
            import _usage
            _usage.log_exposures(
                [{"item_id": hit.get("experience_id", ""), "layer": "experience",
                  "rank": rank + 1, "source_id": (hit.get("source_refs") or [""])[0]}
                 for rank, hit in enumerate(hits)],
                session_id=str(request.get("session_id") or ""),
                task_id=str(request.get("task_id") or ""), query=prompt,
                ts=str(request.get("timestamp") or ""), retrieval_kind=mode)
        except Exception:
            pass
        return {"status": "ok" if hits else "no_hit", "hits": hits,
                "mode": mode,
                "advisory": mode == "failure" and bool(hits)}
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
