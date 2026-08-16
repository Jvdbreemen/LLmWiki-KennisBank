#!/usr/bin/env python3
"""rerank-ceiling.py - what could a perfect reranker of the top-N reach?

TASK-138 is measurement first: do not build a reranker until the ceiling says
whether it is worth building. This computes that ceiling on the pool the
PRODUCTION path actually retrieves.

The ceiling is one probability, not four numbers. A perfect reranker puts the
gold memory at rank 1 whenever it is anywhere in the pool, so for a pool of
size N:

    ceiling@1 == ceiling@5 == P(gold in top-N)

One retrieval per question at the largest N therefore yields every smaller N as
well, plus the rank histogram that says whether a reranker has to be excellent
or merely adequate.

WHY THE POOL SIZE IS REPORTED, AND NOT ONLY THE RANK. `recall_hits` applies a
similarity FLOOR (`MEMORY_MIN_COS`) as well as a top-k. Ask for fifty and the
floor may hand back twelve. A "top-50 ceiling" measured without noticing that
is a number production can never reach, and the honest response is not to drop
the floor for the measurement -- it is to report that the floor, not the
ranking, is the binding constraint. So every question records the pool size it
actually got.

Read-only. Query vectors are cached and keyed by embedding-model identity, so a
model change discards the cache instead of silently mixing vector spaces.

Usage:
    python3 rerank-ceiling.py --set <memory-eval-set.json> [--out ceiling.json]
                             [--pool 50] [--split dev|holdout|all] [--cache q.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path

# NOTE: deliberately no os.environ.setdefault("KENNISBANK_VAULT", ...) here.
# Vault resolution flows through `_vaultpath.vault_root()`, whose
# `_script_vault()` only matches the installed layout (grandparent NAMED
# `.claude`). A bare parents[2] setdefault had no such guard, so in a repo
# checkout it pointed the vault at the directory ABOVE the repo and every
# later caller inherited that -- including tests, which import this module
# at collection time (TASK-167/181).
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import _embeddings as emb  # noqa: E402
from _progress import Progress  # noqa: E402

#: The split that every L2 measurement used, kept identical so this ceiling can
#: sit beside those numbers. 1224 questions, 70/30, seed 42 -> 856 dev.
SPLIT_SEED = 42
SPLIT_DEV_FRACTION = 0.7


def _load(filename: str):
    """Import a hyphenated sibling script by path."""
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""),
        os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_questions(questions: list, which: str = "dev") -> list:
    """The 70/30 split, reproduced from the seed rather than from a file.

    The original dev.json no longer exists. The COUNT reproduces exactly (856),
    but question-level identity with the earlier runs cannot be confirmed
    without that file, and this is stated in the report rather than assumed
    away. It does not affect a within-run comparison, which is all this
    measurement makes.
    """
    if which == "all":
        return list(questions)
    idx = list(range(len(questions)))
    random.Random(SPLIT_SEED).shuffle(idx)
    cut = int(len(questions) * SPLIT_DEV_FRACTION)
    keep = set(idx[:cut] if which == "dev" else idx[cut:])
    return [q for i, q in enumerate(questions) if i in keep]


def gold_rank(pool: list, expect) -> int:
    """1-based rank of the expected memory in the pool, or 0 if absent.

    `expect` may list several acceptable answers; the best-ranked one counts,
    because a reranker only has to surface one of them.
    """
    wanted = expect if isinstance(expect, list) else [expect]
    best = 0
    for w in wanted:
        if w in pool:
            r = pool.index(w) + 1
            best = r if best == 0 else min(best, r)
    return best


def measure(questions: list, pool_size: int, cache, kb_recall,
            min_cos=None) -> list:
    """One retrieval per question; everything else is read off afterwards."""
    rows = []
    with Progress(len(questions), f"retrieving a pool of {pool_size}") as p:
        for item in questions:
            p.step()
            q = item.get("q", "")
            qv = cache.get_or_embed(q, emb.embed)
            if qv is None:
                rows.append({"q": q, "expect": item.get("expect"), "pool": 0,
                             "rank": 0, "type": item.get("type", ""),
                             "embed_failed": True})
                continue
            floor = (kb_recall.MEMORY_MIN_COS if min_cos is None else min_cos)
            hits = kb_recall.recall_hits(
                qv, query_text=q, k=pool_size, layers=("memory",),
                min_cos=floor)
            stems = [Path(h["path"]).stem for h in hits]
            # The cheapest possible reranker: re-sort the SAME pool by raw
            # cosine, discarding the recency and importance re-weighting that
            # _rank applies on top of the RRF score. Free on the hot path, and
            # it answers a question worth answering on its own -- whether that
            # re-weighting earns its place at small k.
            by_cos = [Path(h["path"]).stem
                      for h in sorted(hits, key=lambda h: -h.get("cos", 0.0))]
            rows.append({"q": q, "expect": item.get("expect"),
                         "type": item.get("type", ""),
                         "pool": len(stems),
                         "rank": gold_rank(stems, item.get("expect")),
                         "rank_cos": gold_rank(by_cos, item.get("expect"))})
    return rows


def mcnemar(rows: list, k: int, a: str = "rank", b: str = "rank_cos") -> dict:
    """Exact paired test on hit@k, both directions.

    An average hides displacement: an arm that gains twenty and loses eighteen
    reads as a win. The discordant counts and an exact binomial p-value say
    whether the difference is worth anything.
    """
    from math import comb
    gained = lost = 0
    for r in rows:
        was = 0 < r.get(a, 0) <= k
        now = 0 < r.get(b, 0) <= k
        if was and not now:
            lost += 1
        elif now and not was:
            gained += 1
    n = gained + lost
    if n == 0:
        return {"gained": 0, "lost": 0, "p": 1.0}
    lo = min(gained, lost)
    p = min(1.0, 2.0 * sum(comb(n, i) for i in range(lo + 1)) / (2 ** n))
    return {"gained": gained, "lost": lost, "p": round(p, 6)}


def summarise(rows: list, pool_size: int) -> dict:
    n = len(rows) or 1
    found = [r for r in rows if r["rank"] > 0]

    def at(k):
        return sum(1 for r in rows if 0 < r["rank"] <= k) / n

    pools = sorted(r["pool"] for r in rows)
    ranks = sorted(r["rank"] for r in found)
    ceilings = {str(k): round(at(k), 4) for k in (5, 20, 50) if k <= pool_size}
    return {
        "questions": len(rows),
        "requested_pool": pool_size,
        # The ceiling: a perfect reranker of the top-N puts gold at rank 1
        # whenever it is in the pool, so this is both ceiling@1 and ceiling@5.
        "ceiling": ceilings,
        "baseline": {"recall@1": round(at(1), 4), "recall@5": round(at(5), 4)},
        "reachable_beyond_5": round(at(pool_size) - at(5), 4),
        "pool_size": {
            "median": pools[len(pools) // 2] if pools else 0,
            "p10": pools[int(0.10 * (len(pools) - 1))] if pools else 0,
            "p90": pools[int(0.90 * (len(pools) - 1))] if pools else 0,
            "max": pools[-1] if pools else 0,
            "at_requested": sum(1 for p in pools if p >= pool_size),
        },
        "rank_when_found": {
            "n": len(ranks),
            "median": ranks[len(ranks) // 2] if ranks else 0,
            "p90": ranks[int(0.90 * (len(ranks) - 1))] if ranks else 0,
            "max": ranks[-1] if ranks else 0,
        },
        "absent_from_pool": sum(1 for r in rows if r["rank"] == 0),
        # The cheap arm, measured on the same pool in the same pass.
        "arm_cosine_only": {
            "recall@1": round(sum(1 for r in rows if r.get("rank_cos") == 1) / n, 4),
            "recall@5": round(sum(1 for r in rows
                                  if 0 < r.get("rank_cos", 0) <= 5) / n, 4),
            "mcnemar@5": mcnemar(rows, 5),
            "mcnemar@1": mcnemar(rows, 1),
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ceiling for reranking the top-N")
    ap.add_argument("--set", dest="set_path", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--pool", type=int, default=50)
    ap.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    ap.add_argument("--cache", default="")
    ap.add_argument("--min-cos", type=float, default=None,
                    help="override the production floor; use to separate a "
                         "ranking problem from a floor problem")
    args = ap.parse_args(argv)

    scene_exp = _load("scene-experiment.py")
    kb_recall = _load("kb-recall.py")

    questions = json.loads(Path(args.set_path).read_text(encoding="utf-8"))
    if isinstance(questions, dict):
        questions = questions.get("questions", [])
    chosen = split_questions(questions, args.split)

    cache_path = Path(args.cache) if args.cache else Path("rerank-ceiling-cache.json")
    cache = scene_exp.QueryCache(cache_path, emb.embed_id())

    started = time.monotonic()
    rows = measure(chosen, args.pool, cache, kb_recall, args.min_cos)
    cache.save()
    report = summarise(rows, args.pool)
    report["split"] = args.split
    report["set"] = Path(args.set_path).name
    report["total_questions_in_set"] = len(questions)
    report["embed_id"] = emb.embed_id()
    report["min_cos"] = (kb_recall.MEMORY_MIN_COS if args.min_cos is None
                         else args.min_cos)
    report["min_cos_is_production"] = args.min_cos is None
    report["seconds"] = round(time.monotonic() - started, 1)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(
            json.dumps({"summary": report, "results": rows},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nper-question detail: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
