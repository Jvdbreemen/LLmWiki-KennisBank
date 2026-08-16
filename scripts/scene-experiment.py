#!/usr/bin/env python3
"""scene-experiment.py - run one L2 scene arm and store its full result.

An arm is (clusterer, scene_floor, scene_boost). Two design choices make the
comparison honest and affordable:

SCORING IS NOT REIMPLEMENTED. The report comes from kb-eval's own evaluate(),
which takes an injectable hits_fn. Recall, MRR and the per-type breakdown are
therefore computed by the same code that produces the authoritative numbers --
a second implementation would be free to drift, and drift between harness and
production is the exact failure kb-eval exists to prevent.

QUERY EMBEDDINGS ARE CACHED. Embedding 856 questions costs about seven minutes
and yields the same vectors for every arm, because an arm changes retrieval,
never the query. Caching them turns a ten-arm sweep from over an hour into a
few minutes. The cache is keyed by embedding-model identity, so a model change
invalidates it rather than silently mixing vector spaces.

Usage:
    python3 scene-experiment.py --set SET.json --out arm.json \\
        [--clusterer community] [--floor 0.35] [--boost 0.0] [--no-prior]

See docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md (TASK-134).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)


def _load(filename: str):
    """Import a hyphenated sibling script by path."""
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""),
        os.path.join(SCRIPTS, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# QueryCache verhuisde naar _querycache.py (TASK-190); de re-export houdt
# scene_exp.QueryCache-consumenten (tests, oudere harnas-runs) werkend.
from _querycache import QueryCache  # noqa: E402


def build_hits_fn(kb_recall, cache, embed_fn, scene_prior):
    """hits_fn(q, k) -> [stem], on the production memory-recall route.

    Mirrors kb-eval._live_hits_fn for the memory layer: same recall_hits call,
    same MEMORY_MIN_COS floor. The only difference is where the query vector
    comes from.
    """
    def hits_fn(q: str, k: int) -> list:
        qv = cache.get_or_embed(q, embed_fn)
        if qv is None:
            return []
        rows = kb_recall.recall_hits(qv, query_text=q, k=k, layers=("memory",),
                                     min_cos=kb_recall.MEMORY_MIN_COS,
                                     scene_prior=scene_prior)
        return [Path(r["path"]).stem for r in rows]
    return hits_fn


def flips(baseline: dict, arm: dict) -> dict:
    """Questions that changed outcome, in both directions.

    An average hides displacement: an arm that gains five answers and loses
    four still reads as a win. Both lists belong in the report.
    """
    base = {r["q"]: r for r in baseline.get("results", [])}
    gained, lost = [], []
    for r in arm.get("results", []):
        was = base.get(r["q"])
        if was is None:
            continue
        was_hit = 0 < was.get("rank", 0) <= 5
        now_hit = 0 < r.get("rank", 0) <= 5
        if was_hit == now_hit:
            continue
        entry = {"q": r["q"], "expect": r["expect"], "type": r.get("type", ""),
                 "rank_before": was.get("rank", 0), "rank_after": r.get("rank", 0),
                 "hits_after": r.get("hits", [])}
        (gained if now_hit else lost).append(entry)
    return {"gained": gained, "lost": lost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="run one L2 scene arm")
    ap.add_argument("--set", dest="set_path", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clusterer", default="community")
    ap.add_argument("--floor", type=float, default=0.35)
    ap.add_argument("--boost", type=float, default=0.0)
    ap.add_argument("--seeds", type=int, default=1,
                    help="how many top hits may nominate a scene")
    ap.add_argument("--no-prior", action="store_true",
                    help="baseline arm: no scene prior at all")
    ap.add_argument("--cache", default=None,
                    help="query-embedding cache file (default: beside --out)")
    ap.add_argument("--usage-snapshot", default=None,
                    help="freeze usage telemetry: snapshot kb-usage.db here on "
                         "first use and read it for every arm")
    args = ap.parse_args(argv)

    # An eval must never count as usage. Usage telemetry feeds the recall
    # ranking, so a run that logs its own recalls is measuring a signal it just
    # moved -- and the first version of this driver did exactly that: it scored
    # 0.352@1 where kb-eval scored 0.357 on the same questions, because kb-eval
    # disables telemetry and this did not. Set BEFORE kb-recall is imported, so
    # the module sees it at load time.
    saved_disable = os.environ.get("KB_USAGE_DISABLE")
    os.environ["KB_USAGE_DISABLE"] = "1"
    print("scene-experiment: usage telemetry OFF (KB_USAGE_DISABLE=1)",
          file=sys.stderr)

    # Freeze the usage signal. KB_USAGE_DISABLE stops telemetry being WRITTEN,
    # but _usage.stats_for() reads the live database unconditionally, and the
    # ranking weighs recall by it. That database changes whenever the vault is
    # used, so two runs minutes apart rank differently: measured here as
    # 0.357@1 against 0.350@1 on identical questions and an unchanged index,
    # with zero divergence when both routes ran in one process. Every arm must
    # therefore read the same frozen snapshot, or the experiment compares
    # clock time as much as clustering.
    frozen = None
    if args.usage_snapshot:
        import _usage
        frozen = Path(args.usage_snapshot)
        if not frozen.exists():
            frozen.parent.mkdir(parents=True, exist_ok=True)
            live = _usage.db_path()
            if live.exists():
                shutil.copy2(live, frozen)
                print(f"scene-experiment: usage snapshot taken -> {frozen}",
                      file=sys.stderr)
        _usage.db_path = lambda: frozen
        print(f"scene-experiment: usage telemetry frozen at {frozen.name}",
              file=sys.stderr)

    import _embeddings as emb
    kb_eval = _load("kb-eval.py")
    kb_recall = _load("kb-recall.py")

    entries = kb_eval.load_set(Path(args.set_path))
    if emb.embed("ping") is None:
        print("embedding backend unreachable (is Ollama running?)", file=sys.stderr)
        return 1

    cache_path = Path(args.cache) if args.cache else \
        Path(args.out).with_name("query-vectors.json")
    cache = QueryCache(cache_path, emb.query_embed_id())

    prior = (None if args.no_prior else
         {"floor": args.floor, "boost": args.boost, "seeds": args.seeds})
    hits_fn = build_hits_fn(kb_recall, cache, emb.embed_query, prior)

    t0 = time.perf_counter()
    report = kb_eval.evaluate(entries, hits_fn, measure_latency=True)
    elapsed = time.perf_counter() - t0
    cache.save()

    report["arm"] = {
        "clusterer": None if args.no_prior else args.clusterer,
        "floor": None if args.no_prior else args.floor,
        "boost": None if args.no_prior else args.boost,
        "seeds": None if args.no_prior else args.seeds,
        "prior": not args.no_prior,
    }
    report["set"] = Path(args.set_path).name
    report["cache"] = {"hits": cache.hits, "misses": cache.misses}
    report["wall_seconds"] = round(elapsed, 1)
    if saved_disable is None:
        os.environ.pop("KB_USAGE_DISABLE", None)
    else:
        os.environ["KB_USAGE_DISABLE"] = saved_disable
    report["usage_telemetry"] = "disabled_during_run"
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(json.dumps({"recall": report["recall"], "mrr": report["mrr"],
                      "latency_ms": report.get("latency_ms", {}),
                      "cache": report["cache"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
