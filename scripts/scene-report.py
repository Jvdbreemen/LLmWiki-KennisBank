#!/usr/bin/env python3
"""scene-report.py - diagnostics and the oracle ceiling for the L2 scene layer.

Two read-only measurements that belong BEFORE an expensive arm run:

  diagnostics    -- the shape of the clustering. A clusterer that produces one
                    900-member scene is hopeless by construction, and that is
                    visible here without spending a retrieval sweep.
  oracle_ceiling -- of the questions the baseline currently MISSES, how many
                    have their gold memory in the same scene as a memory the
                    baseline did retrieve? That is the upper bound on what the
                    prior can ever recover. A ceiling below the winner
                    threshold means the arm cannot qualify and need not run.

Usage:
    python3 scene-report.py --total 1428 --json
    python3 scene-report.py --baseline arm-off.json --set dev.json --json

See docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md (TASK-134).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scenes  # noqa: E402


def diagnostics(scene_conn, total_memories: int) -> dict:
    """Scene count, size distribution, coverage, singleton share."""
    sizes = [r[0] for r in scene_conn.execute("SELECT size FROM scenes").fetchall()]
    covered = scene_conn.execute(
        "SELECT count(DISTINCT path) FROM scene_members").fetchone()[0]
    if not sizes:
        return {"scenes": 0, "median_size": 0, "p95_size": 0, "largest": 0,
                "coverage": 0.0, "singletons": 0, "covered": 0}
    ordered = sorted(sizes)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return {
        "scenes": len(sizes),
        "median_size": statistics.median(ordered),
        "p95_size": ordered[idx],
        "largest": ordered[-1],
        "covered": covered,
        "coverage": round(covered / total_memories, 3) if total_memories else 0.0,
        "singletons": sum(1 for s in sizes if s == 1),
    }


def scene_by_stem(scene_conn) -> dict:
    """{file stem: scene_id}. Eval sets identify documents by stem."""
    out = {}
    for path, sid in scene_conn.execute(
            "SELECT path, scene_id FROM scene_members"):
        out[Path(path).stem] = sid
    return out


def oracle_ceiling(scene_conn, results, k: int = 5) -> dict:
    """Upper bound on what the scene prior can recover, from a baseline run.

    ``results`` is kb-eval's per-question list: {"expect": [...], "rank": int,
    "hits": [stem, ...]}.

    The prior can only ever help a question the baseline MISSES, and only when
    the gold memory shares a scene with something the baseline DID retrieve --
    that is the sole route by which a below-floor memory gets admitted. Counting
    anything else would overstate the ceiling.
    """
    by_stem = scene_by_stem(scene_conn)
    misses = [r for r in results if not (0 < r.get("rank", 0) <= k)]
    reachable = 0
    for r in misses:
        hit_scenes = {by_stem.get(s) for s in r.get("hits", [])}
        hit_scenes.discard(None)
        if not hit_scenes:
            continue
        if any(by_stem.get(stem) in hit_scenes for stem in r.get("expect", [])):
            reachable += 1
    n = len(results)
    return {
        "questions": n,
        "misses": len(misses),
        "reachable": reachable,
        "ceiling_delta": round(reachable / n, 3) if n else 0.0,
        "ceiling_recall": round((n - len(misses) + reachable) / n, 3) if n else 0.0,
    }


def _load_report(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    data = json.loads(text[text.find("{"):])
    return data.get("memory", data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="scene diagnostics and oracle ceiling")
    ap.add_argument("--total", type=int, default=0,
                    help="number of current memory documents (for coverage)")
    ap.add_argument("--baseline", default=None,
                    help="a baseline arm report with per-question results")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    conn = _scenes.connect()
    try:
        out = {"diagnostics": diagnostics(conn, args.total)}
        row = conn.execute("SELECT clusterer FROM scenes LIMIT 1").fetchone()
        out["clusterer"] = row[0] if row else None
        if args.baseline:
            report = _load_report(args.baseline)
            results = report.get("results")
            if not results:
                print("baseline report has no per-question results "
                      "(use scene-experiment.py, not kb-eval --json)",
                      file=sys.stderr)
                return 1
            out["oracle"] = oracle_ceiling(conn, results)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        d = out["diagnostics"]
        print(f"clusterer: {out['clusterer']}")
        print(f"scenes: {d['scenes']}  median {d['median_size']}  "
              f"p95 {d['p95_size']}  largest {d['largest']}")
        print(f"coverage: {d['covered']} docs ({d['coverage']:.1%})  "
              f"singletons: {d['singletons']}")
        if "oracle" in out:
            o = out["oracle"]
            print(f"oracle: {o['misses']} misses, {o['reachable']} reachable "
                  f"-> ceiling +{o['ceiling_delta']:.3f} "
                  f"(recall@5 max {o['ceiling_recall']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
