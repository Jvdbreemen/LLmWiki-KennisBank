#!/usr/bin/env python3
"""TASK-209: opt-in local observations, never a sweep or production cache.

All commands print JSON to stdout and write no files. Keep per-document hash
observations local; publish only aggregate results. A changed heartbeat is not
proof that a sweep caused changes between two observations.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from _embeddings import EMBED_DOC_CAP, HASH_HEX
from _frontmatter import parse_frontmatter
from _vaultpath import vault_root

TEXT_CONTRACT = f"sha256-{HASH_HEX};doc_text;strip;cap={EMBED_DOC_CAP};universal-newlines"


def signature(path):
    try:
        st = path.stat()
        return st.st_size, st.st_mtime_ns, st.st_ino
    except FileNotFoundError:
        return None


def read_stable(path):
    before = signature(path)
    data = path.read_bytes()
    if before != signature(path):
        raise ValueError("input changed while being read; retry during idle time")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()[:HASH_HEX]


def record(raw):
    # Path.read_text(), used by doc_text(), performs universal newline decoding.
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    fm, body = parse_frontmatter(text)
    text = body.strip()[:EMBED_DOC_CAP]
    return {"text_hash": digest(text.encode("utf-8")) if text else "",
            "file_hash": digest(raw), "status": fm.get("status", "")}


def heartbeat(vault):
    path = vault / ".claude" / "memory-sweep-status.json"
    if not path.exists():
        return None
    return json.loads(read_stable(path)).get("last_run")


def snapshot(vault):
    vault = Path(vault).resolve()
    directory = vault / "09-memory"
    if not directory.is_dir():
        raise ValueError("09-memory directory is missing")
    run_before = heartbeat(vault)
    paths = sorted(directory.rglob("*.md"))
    signatures = {path: signature(path) for path in paths}
    records = {}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError("memory symlink or path outside 09-memory; refusing scan")
        key = hashlib.sha256(path.relative_to(vault).as_posix().encode()).hexdigest()
        records[key] = record(read_stable(path))
    if (paths != sorted(directory.rglob("*.md"))
            or any(signature(p) != s for p, s in signatures.items())
            or run_before != heartbeat(vault)):
        raise ValueError("corpus or heartbeat changed during observation; retry idle")
    return {"schema": 1, "kind": "filesystem observation",
            "text_contract": TEXT_CONTRACT,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "heartbeat_last_run": run_before, "records": records,
            "memory_files": len(records),
            "statuses": dict(Counter(r["status"] for r in records.values())),
            "natural_sweep_runs_proven": 0}


def compare(before, after):
    if (before.get("schema") != 1 or after.get("schema") != 1
            or before.get("text_contract") != TEXT_CONTRACT
            or after.get("text_contract") != TEXT_CONTRACT):
        raise ValueError("incompatible snapshot schema or text contract")
    a, b = before["records"], after["records"]
    common = a.keys() & b.keys()
    return {"kind": "observation interval; sweep attribution unverified",
            "before_count": len(a), "after_count": len(b), "common": len(common),
            "added": len(b.keys() - a.keys()), "removed": len(a.keys() - b.keys()),
            "text_hash_changed": sum(a[p]["text_hash"] != b[p]["text_hash"]
                                     for p in common),
            "file_only_changed": sum(a[p]["text_hash"] == b[p]["text_hash"]
                                     and a[p]["file_hash"] != b[p]["file_hash"]
                                     for p in common),
            "status_changed": sum(a[p]["status"] != b[p]["status"] for p in common),
            "same_observation": before == after,
            "heartbeat_changed": before.get("heartbeat_last_run")
                                 != after.get("heartbeat_last_run"),
            "natural_sweep_runs_proven": 0}


def compare_cache_records(before, after):
    common = before.keys() & after.keys()
    result = {"kind": "cache artifact interval; sweep attribution unverified",
              "common": len(common), "added": len(after.keys() - before.keys()),
              "removed": len(before.keys() - after.keys()), "text_hash_changed": 0,
              "text_hash_unchanged": 0, "incomparable_hash": 0,
              "embedding_space_changed": 0, "natural_sweep_runs_proven": 0}
    for key in common:
        a, b = before[key], after[key]
        if (a.get("id"), a.get("dim")) != (b.get("id"), b.get("dim")):
            result["embedding_space_changed"] += 1
            continue
        ah, bh = a.get("text_hash", ""), b.get("text_hash", "")
        if (not isinstance(ah, str) or not isinstance(bh, str)
                or len(ah) != len(bh) or len(ah) not in (8, HASH_HEX)
                or any(c not in "0123456789abcdef" for c in ah + bh)):
            result["incomparable_hash"] += 1
            continue
        result["text_hash_changed" if ah != bh else "text_hash_unchanged"] += 1
    return result


def cache_observation(path):
    started = time.perf_counter()
    raw = read_stable(Path(path))
    cache = json.loads(raw)
    if not isinstance(cache, dict):
        raise ValueError("cache must be an object")
    memory = {p: {k: e.get(k) for k in ("id", "dim", "text_hash")}
              for p, e in cache.items()
              if "/09-memory/" in p.replace("\\", "/") and isinstance(e, dict)}
    summary = {"bytes": len(raw), "entries": len(cache), "memory_entries": len(memory),
               "text_hash_widths": dict(Counter(len(e.get("text_hash") or "")
                                                for e in memory.values())),
               "embedding_ids": dict(Counter(e.get("id") for e in memory.values())),
               "read_parse_seconds": time.perf_counter() - started}
    return memory, summary


@contextmanager
def index_image(path, *, load_vec=True):
    """Deserialize a stable idle DB image; never open the source using SQLite.

    Even mode=ro can create/update WAL shared-memory files. Read bytes instead,
    refuse nonempty journals, and change WAL header bytes only in the RAM copy.
    This measures an in-memory image, not cold-disk latency.
    """
    path = Path(path)
    guards = [path, Path(str(path) + "-wal"), Path(str(path) + "-journal")]
    before = [signature(p) for p in guards]
    if any(s and s[0] for s in before[1:]):
        raise ValueError("active WAL/journal; retry after the existing writer finishes")
    data = bytearray(read_stable(path))
    if before != [signature(p) for p in guards]:
        raise ValueError("database/WAL changed during image read; retry idle")
    if data[:16] != b"SQLite format 3\x00":
        raise ValueError("not a SQLite database")
    data[18:20] = b"\x01\x01"
    conn = sqlite3.connect(":memory:")
    try:
        conn.deserialize(bytes(data))
        if load_vec:
            import _kbindex
            conn.enable_load_extension(True)
            try:
                conn.load_extension(_kbindex.vec0_extension())
            finally:
                conn.enable_load_extension(False)
        conn.execute("PRAGMA query_only=ON")
        yield conn
    finally:
        conn.close()


class BudgetExceeded(BaseException):
    """Escape the production arm's broad Exception handler without a fallback."""


class CountedConnection:
    def __init__(self, conn, max_seconds):
        self.conn = conn
        self.started = time.perf_counter()
        self.deadline = self.started + max_seconds
        self.windows = Counter()

    def execute(self, sql, parameters=()):
        if time.perf_counter() >= self.deadline:
            raise BudgetExceeded()
        if "embedding MATCH" in sql:
            self.windows[int(parameters[1])] += 1
        return self.conn.execute(sql, parameters)


def measure(conn, *, vault, max_seconds=45, threshold=0.75):
    """Time the production indexed neighbour arm on its complete current set.

    No current_items(), no cache access, no embeddings, no fallback. Stale and
    missing files are reported; stored vectors stay an explicitly labelled
    index snapshot and are never offered as current memory evidence.
    """
    import _maintenance
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    if meta.get("unit_norm") != "1":
        raise ValueError("index must declare unit_norm=1")
    if not meta.get("embed_id"):
        raise ValueError("index embedding space is missing")
    vault = Path(vault).resolve()
    started = time.perf_counter()
    items, hashes = [], []
    for path, fhash, blob in conn.execute(
            "SELECT d.path, d.hash, v.embedding FROM docs d "
            "JOIN vec_docs v ON v.doc_id=d.doc_id "
            "WHERE d.layer='memory' AND d.status='current' ORDER BY d.path"):
        vector = array.array("f")
        vector.frombytes(blob)
        if len(vector) != int(meta["dim"]):
            raise ValueError("index vector dimension mismatch")
        items.append({"path": str(path), "vec": list(vector)})
        hashes.append(fhash)
    matches, mismatches, incomparable, outside = 0, 0, 0, 0
    for item, fhash in zip(items, hashes):
        path = Path(item["path"])
        if not path.resolve().is_relative_to(vault / "09-memory"):
            outside += 1
            continue
        if (not isinstance(fhash, str) or len(fhash) != HASH_HEX
                or any(c not in "0123456789abcdef" for c in fhash)):
            # A legacy file-hash algorithm is not comparable with SHA-256.
            # Do not label every note stale merely because migration is pending.
            incomparable += 1
            continue
        try:
            agrees = digest(read_stable(path)) == fhash
            matches += agrees
            mismatches += not agrees
        except OSError:
            mismatches += 1
    preparation = time.perf_counter() - started
    counted = CountedConnection(conn, max_seconds)
    pairs, adjacency = None, None
    try:
        adjacency = _maintenance._neighbours_from_index(items, threshold, conn=counted)
        if adjacency is None:
            raise ValueError("production indexed arm declined; no fallback permitted")
        pairs = len({tuple(sorted((a, b))) for a, ns in adjacency.items() for b, _ in ns})
    except BudgetExceeded:
        pass
    elapsed = time.perf_counter() - counted.started
    return {"scope": "index snapshot; not a live sweep", "storage": "in-memory image",
            "embed_id": meta["embed_id"], "dimension": int(meta["dim"]),
            "index_docs": conn.execute("SELECT count(*) FROM docs").fetchone()[0],
            "current_index_items": len(items), "live_file_hash_matches": matches,
            "live_file_hash_mismatches": mismatches,
            "live_file_hash_incomparable": incomparable,
            "paths_outside_memory": outside,
            "threshold": threshold, "preparation_seconds": preparation,
            "neighbour_seconds": elapsed, "budget_seconds": max_seconds,
            "completed": adjacency is not None, "knn_queries": sum(counted.windows.values()),
            "query_windows": dict(counted.windows), "undirected_pairs": pairs,
            "historical_reference_seconds": 1432, "historical_reference_items": 4077,
            "natural_sweep_runs_proven": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("snapshot", help="local hash observation to stdout")
    capture.add_argument("--vault", type=Path)
    diff = commands.add_parser("compare", help="compare two local observations")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    cache = commands.add_parser("cache", help="summarize one or compare two cache artifacts")
    cache.add_argument("before", type=Path)
    cache.add_argument("after", type=Path, nargs="?")
    bench = commands.add_parser("benchmark", help="bounded production indexed-arm timing")
    bench.add_argument("--vault", type=Path)
    bench.add_argument("--max-seconds", type=float, default=45)
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            result = snapshot(args.vault or vault_root())
        elif args.command == "compare":
            result = compare(json.loads(read_stable(args.before)),
                             json.loads(read_stable(args.after)))
        elif args.command == "cache":
            before, summary = cache_observation(args.before)
            result = {"before": summary}
            if args.after:
                after, result["after"] = cache_observation(args.after)
                result["delta"] = compare_cache_records(before, after)
        else:
            if not 0 <= args.max_seconds <= 60:
                raise ValueError("max-seconds must be between 0 and 60")
            vault = args.vault or vault_root()
            with index_image(vault / ".claude" / "kb-index.db") as conn:
                result = measure(conn, vault=vault, max_seconds=args.max_seconds)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, ImportError) as exc:
        # File exceptions can contain private paths; report only the class.
        print(json.dumps({"error": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, ValueError)
                          and not isinstance(exc, json.JSONDecodeError)
                          else "input unavailable, unreadable, or incompatible"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
