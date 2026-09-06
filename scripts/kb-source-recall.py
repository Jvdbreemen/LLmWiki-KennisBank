#!/usr/bin/env python3
"""Explicit lexical source search and exact SourceRef resolution gateway."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def label_hits(hits: list[dict], mode: str) -> list[dict]:
    """Label evidence without pretending lexical rank is answer confidence."""
    labeled = []
    for hit in hits:
        item = dict(hit)
        item["retrieval_mode"] = mode
        exact = item.get("retrieval_route") == "exact_ref"
        item["confidence"] = {
            "basis": "exact_ref" if exact else "bm25",
            "best_effort": not exact,
            "fresh": bool(item.get("fresh")),
        }
        labeled.append(item)
    return labeled


def result_flags(hits: list[dict], mode: str, **_unused) -> list[str]:
    """Represent absence and source-state caveats without hiding a result."""
    del mode
    flags = set()
    if not hits:
        flags.add("no_hit")
    for hit in hits:
        state = str(hit.get("source_state") or hit.get("status") or "").lower()
        if state in {"stale", "missing", "unreadable", "redacted", "invalid"}:
            flags.add(state)
        if "supersed" in state or hit.get("superseded_by"):
            flags.add("superseded")
        if bool(hit.get("conflict")) or hit.get("conflict_group"):
            flags.add("conflict")
    return sorted(flags)


def _exact_hit(source, root: Path, ref: dict, mode: str) -> dict:
    resolved = source.hydrate_source_ref(root, ref)
    resolver_status = str(resolved.get("status") or "invalid")
    item = dict(resolved)
    item["source_state"] = "current" if resolver_status == "valid" else resolver_status
    item["retrieval_route"] = "exact_ref"
    item["best_effort"] = False
    item["fresh"] = bool(resolved.get("fresh"))
    if resolver_status != "valid":
        item.pop("passage", None)
    return label_hits([item], mode)[0]


def run(request: dict, *, vault: Path | None = None, **_ignored) -> dict:
    request = dict(request or {})
    mode = str(request.get("mode") or "normal").lower()
    if mode == "normal":
        return {"status": "not_routed", "hits": []}
    if mode == "fallback":
        return {"status": "policy_disabled", "hits": [], "mode": mode}
    if mode not in {"explicit", "verify", "reconstruct"}:
        return {"status": "not_routed", "hits": []}
    try:
        import _settings
        if not _settings.get("source_explicit_recall", False):
            return {"status": "disabled", "hits": []}
        import _source_recall as source
        root = Path(vault) if vault is not None else Path(
            os.environ.get("KENNISBANK_VAULT", "."))
        if mode in {"verify", "reconstruct"}:
            ref = request.get("source_ref")
            if not isinstance(ref, dict):
                return {"status": "invalid", "hits": [], "mode": mode,
                        "reason": "structured source_ref is required"}
            hit = _exact_hit(source, root, ref, mode)
            available = hit.get("source_state") == "current"
            return {
                "status": "ok" if available else "evidence_unavailable",
                "hits": [hit], "mode": mode,
                "flags": result_flags([hit], mode),
            }

        prompt = str(request.get("prompt") or request.get("query") or "").strip()
        if not prompt:
            return {"status": "invalid", "hits": [], "mode": mode}
        db_path = root / ".claude" / "kb-source.db"
        if not db_path.is_file():
            return {"status": "unavailable", "hits": [], "mode": mode}
        conn = source.connect(db_path)
        try:
            hits = source.source_hits(
                conn, query_text=prompt,
                k=max(1, min(int(request.get("k", 5)), 20)),
                source_path=request.get("source_path"), source_root=root)
        finally:
            conn.close()
        hits = label_hits(hits, mode)
        try:
            import _usage
            _usage.log_exposures(
                [{"item_id": hit.get("source_ref_id", ""), "layer": "source",
                  "rank": rank + 1, "source_id": hit.get("source_path", "")}
                 for rank, hit in enumerate(hits)],
                session_id=str(request.get("session_id") or ""),
                task_id=str(request.get("task_id") or ""), query=prompt,
                ts=str(request.get("timestamp") or ""), retrieval_kind=mode)
        except Exception:
            pass
        return {"status": "ok" if hits else "no_hit", "hits": hits,
                "mode": mode, "flags": result_flags(hits, mode),
                "best_effort": True, "retrieval_route": "lexical_fts"}
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
