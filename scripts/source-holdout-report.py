#!/usr/bin/env python3
"""Report source-holdout oracle ceiling without printing reviewed content."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _source_holdout import load_manifest, oracle_report  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--vault", type=Path,
                        help="vault root; defaults to KENNISBANK_VAULT")
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    print(json.dumps(oracle_report(load_manifest(args.manifest), vault),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
