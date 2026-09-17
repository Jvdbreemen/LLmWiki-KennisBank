#!/usr/bin/env python3
"""Inventory approved raw-source roots without exporting source content."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # shipped scripts/; dev tools live in scripts/dev/
from _frontmatter import parse_frontmatter  # noqa: E402
from _source_recall import APPROVED_ROOTS, TEXT_EXTENSIONS  # noqa: E402


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(vault: Path, *, progress: bool = False) -> dict:
    files = []
    extensions = Counter()
    roots = defaultdict(int)
    hashes = defaultdict(int)
    missing_metadata = 0
    redacted = 0
    unreadable = 0
    scanned = 0
    for root in APPROVED_ROOTS:
        directory = Path(vault) / root
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT_EXTENSIONS:
                continue
            rel = path.relative_to(vault).as_posix()
            try:
                data = path.read_bytes()
                raw = data.decode("utf-8")
                file_hash = _hash_bytes(data)
            except (OSError, UnicodeError):
                unreadable += 1
                continue
            scanned += 1
            if progress and scanned % 500 == 0:
                print(f"inventory: scanned {scanned} text files", file=sys.stderr, flush=True)
            files.append(rel)
            extensions[suffix or "<none>"] += 1
            roots[rel.split("/", 1)[0]] += 1
            hashes[file_hash] += 1
            if ".redacted." in path.name.lower() or path.name.lower().endswith(".redacted"):
                redacted += 1
                continue
            try:
                frontmatter, _body = parse_frontmatter(raw)
            except Exception:
                frontmatter = {}
            if not any(frontmatter.get(key) for key in
                       ("session_id", "created", "timestamp", "source_id")):
                missing_metadata += 1
    duplicate_groups = sum(1 for count in hashes.values() if count > 1)
    return {"files": len(files), "text_files": len(files), "binary_files": 0,
            "unreadable_files": unreadable, "redacted_files": redacted,
            "missing_metadata": missing_metadata,
            "duplicate_hash_groups": duplicate_groups,
            "extensions": dict(sorted(extensions.items())),
            "roots": dict(sorted(roots.items()))}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)
    vault = Path(os.environ.get("KENNISBANK_VAULT", "."))
    print(json.dumps(inventory(vault, progress=args.progress), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
