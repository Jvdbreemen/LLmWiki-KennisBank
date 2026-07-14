#!/usr/bin/env python3
"""kb-noise.py - markeer geinjecteerde kennis als ruis (mens-gated, TASK-17).

Het negatieve tegenwicht van de usage-boost: een document dat in je context
werd geinjecteerd maar daar niets te zoeken had, markeer je expliciet als
ruis. De ranking drukt het dan begrensd omlaag (_rank.noise_factor, vloer
0.8) — nooit autonoom, alleen op deze menselijke markering.

Usage:
    python3 kb-noise.py <stem> [<stem> ...]
    python3 kb-noise.py --list          # huidige noise-markeringen

Stems zijn bestandsnamen zonder .md, zoals ze in het retrieval-blok staan
(bv. 'windows-hoge-cpu-load-diagnose' of '2026-07-02-stale-recall-fix').
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _usage  # noqa: E402


def _list() -> int:
    import sqlite3
    from contextlib import closing
    try:
        with closing(sqlite3.connect(str(_usage.db_path()), timeout=5.0)) as conn:
            rows = conn.execute(
                "SELECT stem, noise, injected, last_noise FROM usage "
                "WHERE noise > 0 ORDER BY noise DESC, stem").fetchall()
    except Exception as exc:
        print(f"kb-noise: kan usage-db niet lezen: {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("geen noise-markeringen")
        return 0
    for stem, noise, injected, last in rows:
        print(f"{noise}x (van {injected} injecties, laatst {last}): {stem}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "--list":
        return _list()
    stems = [a.strip().removesuffix(".md") for a in argv if a.strip()]
    n = _usage.mark_noise(stems)
    if n == 0:
        print("kb-noise: niets gemarkeerd (telemetrie uit of fout)", file=sys.stderr)
        return 1
    print(f"gemarkeerd als ruis: {', '.join(stems)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
