#!/usr/bin/env python3
"""Query the KennisBank temporal activity index."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _activity  # noqa: E402


def _emit(result: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_activity.format_markdown(result))
    return 0 if result.get("ok", True) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("KENNISBANK_VAULT", ""))
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("period", nargs="*", help="date/period text, e.g. 'vorige week'")
        p.add_argument("--topic", default="")
        p.add_argument("--project", default="")
        p.add_argument("--max-events", type=int, default=50)

    add_common(sub.add_parser("timeline"))
    add_common(sub.add_parser("watdeedik"))
    add_common(sub.add_parser("what-did-i-do"))
    add_common(sub.add_parser("weeklog"))
    topic = sub.add_parser("topic-timeline")
    topic.add_argument("topic")
    topic.add_argument("period", nargs="*", help="optional date/period text")
    topic.add_argument("--project", default="")
    topic.add_argument("--max-events", type=int, default=80)
    status = sub.add_parser("status")
    status.set_defaults(status=True)

    args = ap.parse_args(argv)
    vault = Path(args.vault) if args.vault else _activity.vault_root()
    if args.cmd == "status":
        data = _activity.index_status(vault)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(
                f"activity-index: ok={data['ok']} events={data['events']} "
                f"sources={data['sources']} stale={data['stale_sources']} db={data['db']}"
            )
            for warning in data.get("warnings", []):
                print(f"WARN: {warning}")
        return 0 if data.get("ok") else 1

    period = " ".join(getattr(args, "period", [])).strip()
    if args.cmd == "timeline":
        result = _activity.timeline(
            period or "today",
            topic=args.topic,
            project=args.project,
            max_events=args.max_events,
            vault=vault,
        )
    elif args.cmd in {"watdeedik", "what-did-i-do"}:
        result = _activity.what_did_i_do(
            period or "today",
            topic=args.topic,
            project=args.project,
            max_events=args.max_events,
            vault=vault,
        )
    elif args.cmd == "weeklog":
        result = _activity.weeklog(
            period or "vorige week",
            topic=args.topic,
            project=args.project,
            max_events=args.max_events,
            vault=vault,
        )
    else:
        result = _activity.topic_timeline(
            args.topic,
            period_text=period or "afgelopen 90 dagen",
            project=args.project,
            max_events=args.max_events,
            vault=vault,
        )
    return _emit(result, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
