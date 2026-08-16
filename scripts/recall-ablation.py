#!/usr/bin/env python3
"""recall-ablation.py - how much of the recall comes from which half?

The recall route is hybrid: `_kbindex.search` fuses a dense cosine ranking and
an FTS ranking with RRF. As long as you only compare whole models, how much
each half contributes stays invisible -- and that determines how much a better
(or worse) embedder can matter at all. If FTS already answers most questions on
its own, the spread between embedding models is small for a reason that has
nothing to do with those models.

Three conditions over the same index and the same eval set:

  hybrid      the production route: dense + FTS
  fts-only    only the lexical ranking enters the RRF fusion
  dense-only  only the vector ranking enters the RRF fusion

An arm is switched off by replacing `_kbindex._rrf` with a variant that ignores
one of the two rankings. An earlier attempt instead fed a random unit vector as
the query, assuming the dense half would then be noise. That did not work: the
dense arm retrieves `min(max(k*4, 20, total), 4096)` documents -- on this corpus
that is ALL of them -- so a noise vector produces a complete random ranking that
RRF happily weighs in. The spread over five draws was 0.10 to 0.30 recall, which
is precisely the evidence that the setup ablated nothing.

Everything after the fusion (status filter, _rank.rerank with recency and
importance, neighbour expansion) stays identical across all three conditions, so
the difference is attributable to the arm and not to the post-processing.

Stdlib only (apart from the index itself). All conditions need a reachable embed
backend, fts-only included: the route computes the query vector regardless.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

KS = (1, 3, 5)


def _load_by_path(filename: str):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""), str(SCRIPTS / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rank_of(stems, expect) -> int:
    want = set(expect)
    for i, s in enumerate(stems, start=1):
        if s in want:
            return i
    return 0


def _metrics(ranks: list) -> dict:
    n = len(ranks)
    if not n:
        return {**{f"@{k}": None for k in KS}, "mrr": None, "n": 0}
    return {**{f"@{k}": round(sum(1 for r in ranks if 0 < r <= k) / n, 3) for k in KS},
            "mrr": round(sum(1.0 / r for r in ranks if r) / n, 3), "n": n}


class ArmSwitch:
    """Context manager that removes one of the two rankings from the RRF fusion.

    `_kbindex.search` builds `rankings = [vec_ranking]` and appends the FTS
    ranking when the query yields a usable FTS expression. Replacing `_rrf`
    lets exactly one arm through without duplicating the search function --
    duplicating it would mean the ablation silently measures something other
    than production after the next change to it.

    keep="fts" on a query without an FTS expression yields an empty fusion and
    therefore no hits; that is the correct outcome (there is no lexical signal
    in that case), not an error."""

    def __init__(self, kbindex, keep: str):
        self.kbindex = kbindex
        self.keep = keep
        self.orig = kbindex._rrf

    def __enter__(self):
        orig, keep = self.orig, self.keep

        def patched(rank_lists, k_const: int = 60):
            if keep == "dense":
                return orig(rank_lists[:1], k_const)
            if keep == "fts":
                return orig(rank_lists[1:], k_const)
            return orig(rank_lists, k_const)

        self.kbindex._rrf = patched
        return self

    def __exit__(self, *exc):
        self.kbindex._rrf = self.orig
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", required=True)
    ap.add_argument("--model", required=True, help="embedding model the index was built with")
    ap.add_argument("--layer", choices=("wiki", "memory"), default="wiki")
    ap.add_argument("--set", dest="set_path", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conditions", default="hybrid,fts-only,dense-only")
    ap.add_argument("--min-cos", type=float, default=0.0,
                    help="similarity floor. 0.0 is rank-only, which compares the "
                         "arms without a threshold deciding the answer; pass the "
                         "production floor to see what users actually get.")
    args = ap.parse_args()

    os.environ["KENNISBANK_VAULT"] = args.vault
    os.environ["KB_EMBED_PROVIDER"] = "ollama"
    os.environ["KB_EMBED_MODEL"] = args.model
    os.environ["KB_USAGE_DISABLE"] = "1"

    import _embeddings as emb
    kb_recall = _load_by_path("kb-recall.py")

    vault = Path(args.vault)
    default = ("kb-eval-set-full.json" if args.layer == "wiki"
               else "kb-memory-eval-set-full.json")
    path = Path(args.set_path) if args.set_path else vault / "06-claude" / default
    entries = json.loads(path.read_text(encoding="utf-8"))
    if args.limit:
        entries = entries[:args.limit]
    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    print(f"ablation [{args.layer}] {len(entries)} questions from {path.name}, "
          f"index={args.model}", flush=True)

    kmax = max(KS)
    out = {"layer": args.layer, "model": args.model, "n": len(entries),
           "set": path.name, "min_cos": args.min_cos, "conditions": {}}

    if emb.embed("ping") is None:
        print("embedding backend unreachable", file=sys.stderr)
        return 1

    # Query vectors once: the three conditions ask the same questions, and
    # re-embedding would only add measurement noise and waiting time.
    vecs = {}
    for e in entries:
        if e["q"] not in vecs:
            vecs[e["q"]] = emb.embed_query(e["q"])
    print(f"  {len(vecs)} query vectors computed", flush=True)

    def run(keep):
        ranks = []
        with ArmSwitch(kb_recall._kbindex, keep):
            for e in entries:
                rows = kb_recall.recall_hits(vecs[e["q"]], query_text=e["q"],
                                             k=kmax, layers=(args.layer,),
                                             min_cos=args.min_cos)
                ranks.append(_rank_of([Path(r["path"]).stem for r in rows], e["expect"]))
        return ranks

    for cond, keep in (("hybrid", "both"), ("fts-only", "fts"),
                       ("dense-only", "dense")):
        if cond not in conds:
            continue
        out["conditions"][cond] = _metrics(run(keep))
        print(f"  {cond:12} {out['conditions'][cond]}", flush=True)

    dest = vault / (f"ablation-{args.layer}-"
                    f"{args.model.replace(':','-').replace('/','_')}"
                    f"-min{args.min_cos}.json")
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nraw: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
