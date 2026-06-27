#!/usr/bin/env python3
"""Query-string retrieval CLI for KennisBank wiki articles.

Shared by thinking-tool commands (/uitdaag, /brug) and any other LLM-driven
command that needs to retrieve relevant wiki articles by text query.

Unlike kb-retrieve.py (UserPromptSubmit hook, stdin JSON -> additionalContext),
this script accepts a query string on the CLI and emits JSON to stdout.

Usage:
    python3 kb-search.py "<query>" [--top N] [--threshold T]

Output: JSON array of objects {"path": ..., "score": ..., "snippet": ...}
        Always JSON (no human-readable mode). Emits [] and exits 0 on any
        failure (fail-open, same contract as kb-retrieve).

Defaults:
    --top        env KB_RETRIEVE_TOP_N  default 3
    --threshold  env KB_RETRIEVE_THRESHOLD  default 0.60

Candidates come from the cached wiki embeddings (recompute=False). Uncached
articles are silently skipped — the SessionStart hook (build-embed-index.py)
warms the cache; calling live embed for every candidate here would be wrong.

The query itself IS embedded live (one-off, intentional).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Allow direct execution and import via _loader alike.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _embeddings import cosine, doc_text, embed, embed_id, load_cache  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


# ---------------------------------------------------------------------------
# Pure core — no I/O, injected vectors, fully testable without Ollama
# ---------------------------------------------------------------------------

def rank(
    query_vec: list,
    candidates: dict,
    top_n: int,
    threshold: float,
) -> list:
    """Rank candidates by cosine similarity to query_vec.

    Args:
        query_vec:  Embedding of the search query.
        candidates: Mapping of path -> vector.
        top_n:      Maximum number of results to return.
        threshold:  Minimum cosine score to include a result.

    Returns:
        List of (path, score) tuples, sorted by score descending,
        filtered to score >= threshold, capped at top_n.
    """
    scored = []
    for path, vec in candidates.items():
        s = cosine(query_vec, vec)
        if s >= threshold:
            scored.append((path, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _num_env(env: str, default):
    raw = os.environ.get(env)
    if raw is None:
        return default
    try:
        return type(default)(str(raw).strip().replace(",", "."))
    except ValueError:
        return default


def _collapse(text: str, cap: int = 200) -> str:
    """Collapse whitespace and truncate to cap chars."""
    return re.sub(r"\s+", " ", text).strip()[:cap]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Search KennisBank wiki articles by semantic similarity.",
    )
    parser.add_argument("query", help="Search query string")
    parser.add_argument(
        "--top",
        type=int,
        default=_num_env("KB_RETRIEVE_TOP_N", 3),
        metavar="N",
        help="Maximum number of results (default: env KB_RETRIEVE_TOP_N or 3)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=_num_env("KB_RETRIEVE_THRESHOLD", 0.60),
        metavar="T",
        help="Minimum cosine score (default: env KB_RETRIEVE_THRESHOLD or 0.60)",
    )
    args = parser.parse_args()

    query = (args.query or "").strip()
    if not query:
        print("[]")
        return

    # Load cache (warmed by SessionStart hook build-embed-index.py).
    try:
        cache = load_cache()
    except Exception:
        cache = {}

    if not cache:
        print("[]")
        return

    eid = embed_id()
    wiki_prefix = str(vault_root() / "02-wiki")

    # Build candidates from cached wiki entries only (recompute=False, skip uncached).
    candidates: dict = {}
    for k, v in cache.items():
        p = Path(k)
        # Wiki articles only; skip index.md and log.md.
        if not k.startswith(wiki_prefix):
            continue
        if p.name in ("index.md", "log.md"):
            continue
        if v.get("id") != eid:
            continue
        vec = v.get("embedding")
        if not vec:
            continue
        candidates[k] = vec

    if not candidates:
        print("[]")
        return

    # Embed the query live (one-off is fine here).
    try:
        qvec = embed(query)
    except Exception:
        qvec = None

    if not qvec:
        # Fail-open: can't embed -> return empty results.
        print("[]")
        return

    # Rank.
    ranked = rank(qvec, candidates, top_n=args.top, threshold=args.threshold)

    # Build output with snippet from doc_text.
    output = []
    for path, score in ranked:
        try:
            raw_text = doc_text(Path(path), cap=4000)
            snippet = _collapse(raw_text, cap=200)
        except Exception:
            snippet = ""
        output.append({"path": path, "score": round(score, 4), "snippet": snippet})

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[]")
