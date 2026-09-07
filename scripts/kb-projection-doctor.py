#!/usr/bin/env python3
"""Read-only health report for source and split experience projections."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience as experience  # noqa: E402
import _experience_maintenance as maintenance  # noqa: E402
import _source_recall as source  # noqa: E402
import _source_ref as source_ref  # noqa: E402


def _source_builder():
    spec = importlib.util.spec_from_file_location(
        "build_source_index", Path(__file__).with_name("build-source-index.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table_names(conn):
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _integrity(conn, *, deep: bool = False) -> str:
    try:
        pragma = "integrity_check" if deep else "quick_check"
        return str(conn.execute(f"PRAGMA {pragma}").fetchone()[0])
    except sqlite3.DatabaseError:
        return "unreadable"


def _meta(conn, key: str, default: str = "unknown") -> str:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    except sqlite3.DatabaseError:
        try:
            row = conn.execute(
                "SELECT value FROM source_meta WHERE key=?", (key,)).fetchone()
        except sqlite3.DatabaseError:
            row = None
    return str(row[0]) if row else default


def _source_inventory(vault: Path):
    current = {}
    redacted = set()
    builder = _source_builder()
    for item in builder.collect_sources(vault):
        rel = item.relative_to(vault).as_posix()
        try:
            digest = hashlib.sha256()
            header_raw = b""
            with item.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    if len(header_raw) < 16_384:
                        header_raw += block[:16_384 - len(header_raw)]
                    digest.update(block)
            # Redaction markers live in the frontmatter. Decode only a bounded
            # prefix and hash the bytes already read instead of reading every
            # potentially large transcript twice.
            header = header_raw.decode("utf-8", errors="ignore")
            if builder._redacted(item, header):
                redacted.add(rel)
            else:
                current[rel] = "sha256:" + digest.hexdigest()
        except OSError:
            continue
    return current, redacted


def _source_health(vault: Path, *, deep_integrity: bool = False,
                   fast: bool = False) -> dict:
    path = vault / ".claude" / "kb-source.db"
    required = {"source_meta", "source_chunks", "source_manifest", "source_fts"}
    if not path.is_file():
        return {"status": "missing", "rebuildable": True, "reason": "index absent"}
    conn = None
    try:
        conn = source.connect(path)
        tables = _table_names(conn)
        if not required <= tables:
            return {"status": "incomplete", "rebuildable": True,
                    "missing_tables": sorted(required - tables),
                    "integrity": _integrity(conn, deep=deep_integrity)}
        doc_count = conn.execute("SELECT count(*) FROM source_manifest").fetchone()[0]
        backend = _meta(conn, "retrieval_backend")
        version = _meta(conn, "source_index_version", _meta(conn, "index_version"))
        vector_tables = sorted(name for name in tables
                               if "vec" in name.lower() or "vector" in name.lower())
        if fast:
            # quick_check and count(*) over the passage table both walk a
            # multi-gigabyte source projection. Fast mode is intentionally a
            # bounded metadata/schema check and labels those scans as skipped.
            return {
                "status": "present", "rebuildable": True,
                "integrity": None, "integrity_mode": "not_checked",
                "schema_version": version, "documents": doc_count,
                "chunks": None, "provenance_chunks": None,
                "provenance_coverage": None,
                "retrieval_backend": backend,
                "forbidden_vector_tables": vector_tables,
                "inventory_check": "not_checked",
                "stale_sources": None, "orphaned_sources": None,
                "missing_sources": None, "redacted_sources": None,
            }
        chunk_count = conn.execute("SELECT count(*) FROM source_chunks").fetchone()[0]
        provenance_chunks = conn.execute(
            "SELECT count(*) FROM source_chunks WHERE source_path<>'' "
            "AND source_hash LIKE 'sha256:%' AND start>=0 AND end>start "
            "AND passage_hash LIKE 'sha256:%'").fetchone()[0]
        manifest = {str(row[0]): str(row[1]) for row in conn.execute(
            "SELECT source_path, source_hash FROM source_manifest")}
        integrity = _integrity(conn, deep=deep_integrity)
        common = {
            "status": "ready" if integrity == "ok" else "unreadable",
            "rebuildable": True, "integrity": integrity,
            "integrity_mode": "deep" if deep_integrity else "quick",
            "schema_version": version, "documents": doc_count,
            "chunks": chunk_count, "provenance_chunks": provenance_chunks,
            "provenance_coverage": (
                provenance_chunks / chunk_count if chunk_count else 1.0),
            "retrieval_backend": backend,
            "forbidden_vector_tables": vector_tables,
        }
        current, redacted = _source_inventory(vault)
        stale = sorted(rel for rel, digest in manifest.items()
                       if rel in current and current[rel] != digest)
        missing = sorted(set(manifest) - set(current) - redacted)
        return {
            **common, "inventory_check": "checked", "stale_sources": stale,
            "orphaned_sources": missing, "missing_sources": missing,
            "redacted_sources": sorted(redacted),
        }
    except Exception as exc:
        return {"status": "unreadable", "rebuildable": True,
                "reason": type(exc).__name__}
    finally:
        if conn is not None:
            conn.close()


def _ledger_health(vault: Path, *, deep_integrity: bool = False) -> dict:
    path = experience.ledger_path(vault)
    required = {"experience_events", "experience_outcomes", "experience_reviews"}
    if not path.is_file():
        return {"status": "missing", "rebuildable": False, "reason": "ledger absent"}
    conn = None
    try:
        conn = experience.connect(path)
        tables = _table_names(conn)
        if not required <= tables:
            return {"status": "incomplete", "rebuildable": False,
                    "missing_tables": sorted(required - tables),
                    "integrity": _integrity(conn, deep=deep_integrity)}
        integrity = _integrity(conn, deep=deep_integrity)
        return {
            "status": "ready" if integrity == "ok" else "unreadable",
            "rebuildable": False, "integrity": integrity,
            "integrity_mode": "deep" if deep_integrity else "quick",
            "schema_version": "1",
            "events": conn.execute(
                "SELECT count(*) FROM experience_events").fetchone()[0],
            "outcomes": conn.execute(
                "SELECT count(*) FROM experience_outcomes").fetchone()[0],
            "reviews": conn.execute(
                "SELECT count(*) FROM experience_reviews").fetchone()[0],
        }
    except Exception as exc:
        return {"status": "unreadable", "rebuildable": False,
                "reason": type(exc).__name__}
    finally:
        if conn is not None:
            conn.close()


def _projection_health(vault: Path, *, live_embed_id: str = "",
                       deep_integrity: bool = False,
                       fast: bool = False) -> dict:
    path = experience.projection_path(vault)
    required = {"experiences", "docs", "fts_docs", "meta"}
    if not path.is_file():
        return {"status": "missing", "rebuildable": True,
                "reason": "projection absent"}
    conn = None
    try:
        conn = experience.connect(path)
        tables = _table_names(conn)
        if not required <= tables:
            return {"status": "incomplete", "rebuildable": True,
                    "missing_tables": sorted(required - tables),
                    "integrity": _integrity(conn, deep=deep_integrity)}
        rows = [experience.experience(conn, str(row[0])) for row in conn.execute(
            "SELECT experience_id FROM experiences ORDER BY experience_id")]
        rows = [row for row in rows if row is not None]
        if fast:
            lifecycle = maintenance.lifecycle_report(rows)
            lifecycle["orphan_experiences"] = None
            lifecycle["redacted_experiences"] = None
        else:
            current, redacted = _source_inventory(vault)
            lifecycle = maintenance.lifecycle_report(
                rows, existing_sources=set(current), redacted_sources=redacted)
        integrity = _integrity(conn, deep=deep_integrity)
        embed_id = _meta(conn, "embed_id", "")
        if embed_id.startswith("lexical-only"):
            compatibility = "lexical_fallback"
        elif not live_embed_id:
            compatibility = "unknown"
        elif embed_id == live_embed_id:
            compatibility = "compatible"
        else:
            compatibility = "mismatch"
        structured = sum(1 for row in rows if row.get("source_refs") and all(
            isinstance(ref, dict) and ref.get("source_ref_id")
            for ref in row.get("source_refs") or []))
        evidence_counts = Counter(str(row.get("evidence_state") or "unknown")
                                  for row in rows)
        review_counts = Counter(str(row.get("review_state") or "unknown")
                                for row in rows)
        resolved_counts = Counter()
        if not fast:
            for row in rows:
                for ref in row.get("source_refs") or []:
                    if isinstance(ref, dict) and ref.get("source_ref_id"):
                        resolved = source_ref.resolve_source_ref(vault, ref)
                        resolved_counts[str(resolved.get("status") or "invalid")] += 1
        lifecycle.update({
            "status": "ready" if integrity == "ok" else "unreadable",
            "rebuildable": True, "integrity": integrity,
            "integrity_mode": "deep" if deep_integrity else "quick",
            "projection_version": _meta(conn, "experience_projection_version"),
            "embed_id": embed_id, "model_compatibility": compatibility,
            "source_ref_coverage": structured / len(rows) if rows else 1.0,
            "evidence_state_counts": dict(sorted(evidence_counts.items())),
            "resolved_source_ref_counts": dict(sorted(resolved_counts.items())),
            "review_state_counts": dict(sorted(review_counts.items())),
            "source_ref_check": "not_checked" if fast else "checked",
            "stale_count": None if fast else int(resolved_counts.get("stale", 0)),
            "missing_count": None if fast else int(resolved_counts.get("missing", 0)),
            "redacted_count": None if fast else int(resolved_counts.get("redacted", 0)),
            "invalid_ref_count": None if fast else int(resolved_counts.get("invalid", 0)),
            "contradictory_count": int(evidence_counts.get("contradictory", 0)),
        })
        return lifecycle
    except Exception as exc:
        return {"status": "unreadable", "rebuildable": True,
                "reason": type(exc).__name__}
    finally:
        if conn is not None:
            conn.close()


def _settings(vault: Path) -> dict:
    try:
        data = json.loads((vault / "kennisbank-settings.json").read_text(
            encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _enabled(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def health(vault, *, live_embed_id: str = "", deep_integrity: bool = False,
           fast: bool = False) -> dict:
    vault = Path(vault)
    settings = _settings(vault)
    forbidden = sorted(key for key in (
        "source_recall", "experience_recall", "source_fallback",
        "experience_failure_advisory") if _enabled(settings.get(key, False)))
    ledger = _ledger_health(vault, deep_integrity=deep_integrity)
    projection = _projection_health(
        vault, live_embed_id=live_embed_id, deep_integrity=deep_integrity,
        fast=fast)
    return {
        "schema_version": 2,
        "inventory_check": "not_checked" if fast else "checked",
        "routes": {
            "source": "enabled" if _enabled(settings.get(
                "source_explicit_recall", False)) else "disabled",
            "experience": "enabled" if _enabled(settings.get(
                "experience_explicit_recall", False)) else "disabled",
        },
        "forbidden_flags": forbidden,
        "source": _source_health(
            vault, deep_integrity=deep_integrity, fast=fast),
        "experience": {"ledger": ledger, "projection": projection},
        "mutated": False,
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    vault = Path(argv[argv.index("--vault") + 1]) if "--vault" in argv else Path(
        os.environ.get("KENNISBANK_VAULT", "."))
    live_embed_id = ""
    try:
        import _embeddings
        live_embed_id = _embeddings.embed_id()
    except Exception:
        pass
    print(json.dumps(health(vault, live_embed_id=live_embed_id,
                            deep_integrity="--deep" in argv,
                            fast="--fast" in argv),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
