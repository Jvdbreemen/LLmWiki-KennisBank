#!/usr/bin/env python3
"""Build or refresh the KennisBank temporal activity index."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _activity  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("KENNISBANK_VAULT", ""))
    ap.add_argument("--full", action="store_true", help="drop and rebuild the index")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--progress-interval",
        type=float,
        default=300.0,
        help="seconds between progress lines during long backfills",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    vault = Path(args.vault) if args.vault else _activity.vault_root()
    stats = _activity.build_activity_index(
        vault,
        full=args.full,
        progress_interval=args.progress_interval,
        verbose=not args.quiet,
    )
    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print(
            "activity-index: "
            f"{stats.get('total_events', 0)} events, "
            f"{stats.get('sources', 0)} sources, "
            f"{stats.get('changed_sources', 0)} changed, "
            f"{stats.get('skipped_sources', 0)} unchanged, "
            f"{stats.get('elapsed_seconds', 0)}s"
        )
        print(f"db: {stats.get('db')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
