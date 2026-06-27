"""Candidate-match helper for the /wiki self-rewrite command.

Given a target article (or a raw query string), find the most similar existing
wiki article by cosine similarity over cached embeddings. The /wiki command uses
this to decide whether to rewrite an existing article instead of creating a
duplicate.

Usage:
    python3 find-similar.py <article-or-text> [--threshold T] [--json]

Arguments:
    article-or-text   Path to a .md file OR a literal query string.
    --threshold T     Similarity threshold (float). Default: $KB_REWRITE_THRESHOLD
                      or 0.62 if that env var is unset.
    --json            Accepted for compatibility; output is always JSON.

Output (JSON):
    {"path": <best path or null>, "score": <float>, "above_threshold": <bool>}

    "path" is the best matching wiki article regardless of threshold.
    "above_threshold" tells the caller whether to act on the match.
    If candidates is empty, path is null and score is 0.0.

Pure core — best_match() — is testable with no network/Ollama by injecting
vectors directly.

Stdlib only (besides the reused _embeddings / _vaultpath helpers).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow direct execution and import via _loader alike.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _embeddings import cosine, doc_text, embed, get_cached, load_cache  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------

SKIP_NAMES = {"index.md", "log.md"}


def best_match(target_vec: list, candidates: dict) -> tuple:
    """Return (path, score) of the highest-cosine candidate.

    candidates maps path -> vector.  Returns (None, 0.0) when candidates is
    empty.  The caller is responsible for excluding the target from candidates
    before calling; best_match itself just ranks what it's given.
    """
    if not candidates:
        return (None, 0.0)
    best_path = None
    best_score = -1.0
    for path, vec in candidates.items():
        score = cosine(target_vec, vec)
        if score > best_score:
            best_score = score
            best_path = path
    return (best_path, float(best_score))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_candidates(wiki_dir: Path, cache: dict, exclude_path: str | None) -> dict:
    """Return {str(path): embedding} for all wiki articles except skipped ones.

    Candidates rely on the warmed embedding cache populated by build-embed-index.py.
    Articles without a cached embedding are skipped to avoid live network calls.
    """
    candidates = {}
    for md in sorted(wiki_dir.glob("*.md")):
        if md.name in SKIP_NAMES:
            continue
        key = str(md)
        if exclude_path and key == exclude_path:
            continue
        vec = get_cached(md, cache, recompute=False)
        if vec:
            candidates[key] = vec
    return candidates


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        prog="find-similar",
        description="Find the closest wiki article to a query or article path.",
    )
    parser.add_argument("query", help="Path to a .md file or a literal query string.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Similarity threshold (default: $KB_REWRITE_THRESHOLD or 0.62).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Accepted for compatibility; output is always JSON.",
    )
    args = parser.parse_args(argv)

    # Resolve threshold
    threshold = args.threshold
    if threshold is None:
        env_val = os.environ.get("KB_REWRITE_THRESHOLD", "").strip()
        try:
            threshold = float(env_val) if env_val else 0.62
        except ValueError:
            threshold = 0.62

    # Load cache once; candidates and (for .md targets) the target itself read from it.
    cache = load_cache()

    # Determine target path or raw text
    query_arg = args.query
    target_path: str | None = None
    target_vec = None

    candidate_exclude = None
    p = Path(query_arg)
    if p.suffix == ".md" and p.exists():
        target_path = str(p.resolve())
        candidate_exclude = target_path
        target_vec = get_cached(p, cache, recompute=True)
    else:
        # Treat as literal query text — must embed live to get the query vector.
        target_vec = embed(query_arg)

    if target_vec is None:
        result = {"path": None, "score": 0.0, "above_threshold": False}
        print(json.dumps(result))
        sys.exit(1)

    # Build candidates from wiki
    wiki_dir = vault_root() / "02-wiki"
    candidates = _build_candidates(wiki_dir, cache, candidate_exclude)

    best_path, best_score = best_match(target_vec, candidates)

    above = best_score >= threshold
    result = {
        "path": best_path,
        "score": round(best_score, 6),
        "above_threshold": above,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
