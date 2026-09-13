#!/usr/bin/env python3
"""Measure warm lexical search and exact SourceRef hydration latency."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source_recall as source  # noqa: E402


def percentile(samples: list[float], fraction: float = 0.95) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction) - 1))
    return ordered[index]


def benchmark(vault: Path, query: str, *, iterations: int = 50, k: int = 5) -> dict:
    vault = Path(vault)
    db = vault / ".claude" / "kb-source.db"
    if not db.is_file():
        return {"status": "unavailable", "reason": "source index absent"}
    conn = source.connect(db)
    try:
        warm = source.source_hits(
            conn, query_text=query, k=k, source_root=vault)
        if not warm:
            return {"status": "no_hit", "query": query}
        search_ms = []
        for _ in range(max(1, int(iterations))):
            started = time.perf_counter()
            source.source_hits(conn, query_text=query, k=k, source_root=vault)
            search_ms.append((time.perf_counter() - started) * 1000)
        ref = warm[0]["source_ref"]
        hydration_ms = []
        for _ in range(max(1, int(iterations))):
            started = time.perf_counter()
            source.hydrate_source_ref(vault, ref)
            hydration_ms.append((time.perf_counter() - started) * 1000)
    finally:
        conn.close()
    search_p95 = percentile(search_ms)
    hydration_p95 = percentile(hydration_ms)
    return {
        "status": "ok",
        "query": query,
        "iterations": max(1, int(iterations)),
        "hits": len(warm),
        "search": {
            "median_ms": round(statistics.median(search_ms), 3),
            "p95_ms": round(search_p95, 3),
            "budget_ms": 250.0,
            "within_budget": search_p95 <= 250.0,
        },
        "exact_hydration": {
            "median_ms": round(statistics.median(hydration_ms), 3),
            "p95_ms": round(hydration_p95, 3),
            "budget_ms": 50.0,
            "within_budget": hydration_p95 <= 50.0,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    result = benchmark(vault, args.query, iterations=args.iterations, k=args.k)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if (
        result.get("status") == "ok"
        and result["search"]["within_budget"]
        and result["exact_hydration"]["within_budget"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
