#!/usr/bin/env python3
"""rank-factors.py - which factor in _rank.rerank costs the recall? (TASK-160)

TASK-138 measured that re-sorting the production pool by raw cosine more than
doubles recall@1 (0.264 -> 0.557, McNemar 272 gained / 21 lost). The loss is
attributable to `_rank.rerank` and nothing else, because the memory layer has
no lexical arm and RRF over a single ranking is order-preserving. This script
says WHICH of its factors carries it.

Method: neutralise one factor at a time and re-run the PRODUCTION retrieval
path. Scoring is never reimplemented -- an arm is `_rank.<factor>` patched to
return 1.0, so every number comes from the code that actually runs. A
reimplementation would be free to drift, and drift between harness and
production is the failure this kind of measurement exists to prevent.

The all-neutral arm is the control. If neutralising every factor does NOT
reproduce the cosine ordering exactly, something outside these factors is also
reordering, and the decomposition is incomplete. That is worth knowing before
any conclusion is drawn from the rest.

Why the factors can dominate at all: RRF scores adjacent ranks at 1/(60+r), so
rank 1 and rank 2 differ by 1.6%. The factors span 0.6-1.0 (recency),
0.9-1.1 (importance), 0.95-1.05 (trust) and 1.0-1.1 (usage) -- a swing far
larger than the gap they are multiplied into.

Read-only. Reuses the query-vector cache, so an arm costs retrieval time only.

Usage:
    python3 rank-factors.py --set <memory-eval-set.json> --cache q.json
                           [--split dev] [--pool 50] [--out factors.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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
import _rank  # noqa: E402
from _progress import Progress  # noqa: E402


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""),
        os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CEIL = _load("rerank-ceiling.py")

#: One entry per arm: which factor functions to neutralise. An empty tuple is
#: production. `_ALL` is the control that must reproduce the cosine ordering.
ARMS = {
    "production": (),
    "no_recency": ("recency_factor",),
    "no_importance": ("importance_factor",),
    "no_trust": ("trust_factor",),
    "no_usage": ("usage_factor",),
    "no_noise": ("noise_factor",),
    "all_neutral": ("recency_factor", "importance_factor", "trust_factor",
                    "usage_factor", "noise_factor"),
    "only_recency": ("importance_factor", "trust_factor", "usage_factor",
                     "noise_factor"),
}


class Neutralised:
    """Patch the named `_rank` factors to return 1.0 for the duration."""

    def __init__(self, names):
        self.names = [n for n in names if hasattr(_rank, n)]
        self.saved = {}

    def __enter__(self):
        for n in self.names:
            self.saved[n] = getattr(_rank, n)
            setattr(_rank, n, lambda *a, **k: 1.0)
        return self

    def __exit__(self, *exc):
        for n, fn in self.saved.items():
            setattr(_rank, n, fn)
        return False


def run_arm(name, questions, pool_size, cache, kb_recall) -> list:
    rows = []
    with Neutralised(ARMS[name]):
        with Progress(len(questions), f"arm {name}") as p:
            for item in questions:
                p.step()
                q = item.get("q", "")
                qv = cache.get_or_embed(q, emb.embed)
                if qv is None:
                    rows.append({"q": q, "rank": 0, "rank_cos": 0, "pool": 0})
                    continue
                hits = kb_recall.recall_hits(
                    qv, query_text=q, k=pool_size, layers=("memory",),
                    min_cos=kb_recall.MEMORY_MIN_COS)
                stems = [Path(h["path"]).stem for h in hits]
                by_cos = [Path(h["path"]).stem
                          for h in sorted(hits, key=lambda h: -h.get("cos", 0.0))]
                rows.append({
                    "q": q, "pool": len(stems),
                    "rank": CEIL.gold_rank(stems, item.get("expect")),
                    "rank_cos": CEIL.gold_rank(by_cos, item.get("expect")),
                })
    return rows


def recalls(rows, field="rank") -> dict:
    n = len(rows) or 1
    return {
        "recall@1": round(sum(1 for r in rows if r.get(field) == 1) / n, 4),
        "recall@5": round(sum(1 for r in rows if 0 < r.get(field, 0) <= 5) / n, 4),
    }


def paired(base_rows, arm_rows, k) -> dict:
    """McNemar between two ARMS, matched on the question text."""
    base = {r["q"]: r for r in base_rows}
    merged = [{"rank": base[r["q"]]["rank"], "rank_cos": r["rank"]}
              for r in arm_rows if r["q"] in base]
    return CEIL.mcnemar(merged, k)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="decompose _rank.rerank")
    ap.add_argument("--set", dest="set_path", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--pool", type=int, default=50)
    ap.add_argument("--out", default="")
    ap.add_argument("--arms", default="")
    args = ap.parse_args(argv)

    scene_exp = _load("scene-experiment.py")
    kb_recall = _load("kb-recall.py")

    questions = json.loads(Path(args.set_path).read_text(encoding="utf-8"))
    if isinstance(questions, dict):
        questions = questions.get("questions", [])
    chosen = CEIL.split_questions(questions, args.split)
    cache = scene_exp.QueryCache(Path(args.cache), emb.embed_id())

    wanted = args.arms.split(",") if args.arms else list(ARMS)
    results, report = {}, {"split": args.split, "questions": len(chosen),
                           "embed_id": emb.embed_id(), "arms": {}}

    for name in wanted:
        started = time.monotonic()
        rows = run_arm(name, chosen, args.pool, cache, kb_recall)
        results[name] = rows
        entry = recalls(rows)
        entry["seconds"] = round(time.monotonic() - started, 1)
        if name != "production" and "production" in results:
            entry["vs_production@1"] = paired(results["production"], rows, 1)
            entry["vs_production@5"] = paired(results["production"], rows, 5)
        report["arms"][name] = entry
        print(f"  {name:16s} recall@1 {entry['recall@1']:.4f}  "
              f"recall@5 {entry['recall@5']:.4f}", flush=True)
    cache.save()

    # The control: all_neutral must reproduce the cosine ordering exactly.
    if "all_neutral" in results:
        rows = results["all_neutral"]
        mismatch = sum(1 for r in rows if r["rank"] != r["rank_cos"])
        report["control"] = {
            "all_neutral_matches_cosine_order": mismatch == 0,
            "questions_where_it_differs": mismatch,
            "note": ("If this is not zero, something outside these factors "
                     "also reorders and the decomposition is incomplete."),
        }

    print("\n" + json.dumps(report, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(
            json.dumps({"report": report, "results": results},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
