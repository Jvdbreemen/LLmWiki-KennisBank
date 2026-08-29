#!/usr/bin/env python3
"""Read-only health report for the source and experience projections."""
from __future__ import annotations

import json
import os
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _experience as experience  # noqa: E402
import _experience_maintenance as maintenance  # noqa: E402
import _source_recall as source  # noqa: E402


def _source_builder():
    spec = importlib.util.spec_from_file_location(
        "build_source_index", Path(__file__).with_name("build-source-index.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table_names(conn):
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _source_health(vault: Path) -> dict:
    path = vault / ".claude" / "kb-source.db"
    required = {"docs", "source_chunks", "source_manifest", "doc_sources"}
    if not path.is_file():
        return {"status": "missing", "rebuildable": True, "reason": "index absent"}
    try:
        conn = source.connect(path)
        tables = _table_names(conn)
        if not required <= tables:
            conn.close()
            return {"status": "incomplete", "rebuildable": True,
                    "missing_tables": sorted(required - tables)}
        doc_count = conn.execute("SELECT count(*) FROM docs WHERE layer='source'").fetchone()[0]
        chunk_count = conn.execute("SELECT count(*) FROM source_chunks").fetchone()[0]
        provenance_docs = conn.execute(
            "SELECT count(*) FROM docs d WHERE d.layer='source' AND EXISTS "
            "(SELECT 1 FROM doc_sources s WHERE s.doc_id=d.doc_id)").fetchone()[0]
        manifest = {str(row[0]): str(row[1]) for row in conn.execute(
            "SELECT source_path, source_hash FROM source_manifest")}
        conn.close()
        current = {}
        redacted = set()
        builder = _source_builder()
        for item in builder.collect_sources(vault):
            rel = item.relative_to(vault).as_posix()
            try:
                text = item.read_text(encoding="utf-8")
                if builder._redacted(item, text):
                    redacted.add(rel)
                else:
                    current[rel] = source.sha256_file(item)
            except (OSError, UnicodeError):
                continue
        stale = sorted(rel for rel, digest in manifest.items()
                       if rel in current and current[rel] != digest)
        orphaned_chunks = sorted(set(manifest) - set(current) - redacted)
        return {"status": "ready", "rebuildable": True, "documents": doc_count,
                "chunks": chunk_count, "provenance_documents": provenance_docs,
                "provenance_coverage": (provenance_docs / doc_count if doc_count else 1.0),
                "stale_sources": stale, "orphaned_sources": orphaned_chunks,
                "redacted_sources": sorted(redacted)}
    except Exception as exc:
        return {"status": "unreadable", "rebuildable": True, "reason": str(exc)}


def _experience_health(vault: Path) -> dict:
    path = vault / ".claude" / "kb-experience.db"
    required = {"experiences", "experience_events", "experience_outcomes"}
    if not path.is_file():
        return {"status": "missing", "rebuildable": True, "reason": "store absent"}
    try:
        conn = experience.connect(path)
        tables = _table_names(conn)
        if not required <= tables:
            conn.close()
            return {"status": "incomplete", "rebuildable": True,
                    "missing_tables": sorted(required - tables)}
        rows = []
        for row in conn.execute(
                "SELECT experience_id, status, source_refs_json, outcome_refs_json "
                "FROM experiences"):
            rows.append({"experience_id": row[0], "status": row[1],
                         "source_refs": json.loads(row[2] or "[]"),
                         "outcome_refs": json.loads(row[3] or "[]")})
        events = conn.execute("SELECT count(*) FROM experience_events").fetchone()[0]
        outcomes = conn.execute("SELECT count(*) FROM experience_outcomes").fetchone()[0]
        conn.close()
        existing = set()
        for item in _source_builder().collect_sources(vault):
            existing.add(item.relative_to(vault).as_posix())
        lifecycle = maintenance.lifecycle_report(rows, existing_sources=existing)
        lifecycle.update({"status": "ready", "rebuildable": True,
                          "events": events, "outcomes": outcomes})
        return lifecycle
    except Exception as exc:
        return {"status": "unreadable", "rebuildable": True, "reason": str(exc)}


def health(vault) -> dict:
    vault = Path(vault)
    settings = {}
    try:
        settings = json.loads((vault / "kennisbank-settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {
        "schema_version": 1,
        "routes": {"source": "enabled" if settings.get("source_recall", False) else "disabled",
                   "experience": "enabled" if settings.get("experience_recall", False) else "disabled"},
        "source": _source_health(vault),
        "experience": _experience_health(vault),
        "mutated": False,
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    vault = Path(argv[argv.index("--vault") + 1]) if "--vault" in argv else Path(
        os.environ.get("KENNISBANK_VAULT", "."))
    print(json.dumps(health(vault), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
