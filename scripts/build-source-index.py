#!/usr/bin/env python3
"""Build the isolated, disposable lexical raw-source projection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source_recall as source  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


APPROVED_ROOTS = source.APPROVED_ROOTS
TEXT_EXTENSIONS = source.TEXT_EXTENSIONS
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_OVERLAP = 200
INDEX_VERSION = source.INDEX_VERSION


def collect_sources(vault: Path) -> list[Path]:
    paths = []
    for root in APPROVED_ROOTS:
        directory = vault / root
        if not directory.is_dir():
            continue
        paths.extend(path for path in directory.rglob("*")
                     if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS)
    return sorted(set(paths), key=lambda path: path.as_posix())


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return source.sha256_file(path)


def _read_source(path: Path) -> tuple[str, str]:
    """Read and hash the same bytes so projection provenance cannot drift."""
    raw = path.read_bytes()
    return raw.decode("utf-8"), _digest(raw)


def chunk_text(text: str, *, size: int = DEFAULT_CHUNK_SIZE,
               overlap: int = DEFAULT_OVERLAP) -> list[dict]:
    return source.chunk_text(text, size=size, overlap=overlap)


def _connect(path: Path) -> sqlite3.Connection:
    return source.connect(path)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    source.ensure_schema(conn)


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO source_meta(key, value) VALUES (?, ?)",
                 (key, str(value)))


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    try:
        row = conn.execute("SELECT value FROM source_meta WHERE key=?", (key,)).fetchone()
    except sqlite3.DatabaseError:
        return None
    return str(row[0]) if row else None


def _manifest(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute(
            "SELECT source_path, source_hash FROM source_manifest"
        ).fetchall()
    except sqlite3.DatabaseError:
        return {}
    return {str(path): str(file_hash) for path, file_hash in rows}


def _is_current_projection(conn: sqlite3.Connection, *, manifest: dict[str, str],
                           chunk_size: int, overlap: int) -> bool:
    required = {"source_meta", "source_manifest", "source_chunks", "source_fts"}
    try:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        healthy = conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except (sqlite3.DatabaseError, TypeError):
        return False
    return (
        healthy
        and required.issubset(names)
        and _manifest(conn) == manifest
        and _meta_get(conn, "source_index_version") == INDEX_VERSION
        and _meta_get(conn, "retrieval_backend") == "sqlite_fts5"
        and _meta_get(conn, "chunk_size") == str(chunk_size)
        and _meta_get(conn, "overlap") == str(overlap)
    )


def _redacted(path: Path, text: str) -> bool:
    if ".redacted." in path.name.lower() or path.name.lower().endswith(".redacted"):
        return True
    header = text[:4000].lower()
    return "redacted:" in header and any(
        token in header for token in ("redacted: true", "redacted: yes", "redacted: 1"))


_SOURCE_METADATA_KEYS = (
    "source_id", "session_id", "timestamp", "date", "created", "project",
    "project_path", "client", "role",
)


def _source_metadata(text: str, relative_path: str) -> dict:
    """Extract a small scalar allowlist; never copy arbitrary frontmatter."""
    metadata = {"source_root": relative_path.split("/", 1)[0]}
    try:
        frontmatter, _body = parse_frontmatter(text)
    except Exception:
        frontmatter = {}
    for key in _SOURCE_METADATA_KEYS:
        value = frontmatter.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            metadata[key] = value
    return metadata


def _insert_source(conn: sqlite3.Connection, *, source_path: str,
                   source_hash: str, chunks: list[dict], metadata: dict) -> int:
    source.upsert_source(
        conn, source_path=source_path, source_hash=source_hash,
        chunks=chunks, metadata=metadata, commit=False)
    return len(chunks)


def _emit(progress_fn, event: dict) -> None:
    """Progress is diagnostic only; a broken reporter must not break a build."""
    if progress_fn is None:
        return
    try:
        progress_fn(dict(event))
    except Exception:
        pass


def _remove_stage_files(stage: Path) -> None:
    for path in (stage, Path(str(stage) + "-wal"), Path(str(stage) + "-shm")):
        if path.exists():
            path.unlink()


def build_source_index(vault: Path, *, rebuild: bool = False,
                       chunk_size: int = DEFAULT_CHUNK_SIZE,
                       overlap: int = DEFAULT_OVERLAP, progress_fn=None) -> dict:
    """Build a deterministic FTS5 projection and atomically publish it."""
    # Validate even for an empty corpus; build parameters are part of the stamp.
    chunk_text("", size=chunk_size, overlap=overlap)
    vault = Path(vault)
    target = vault / ".claude" / "kb-source.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_name(target.name + ".staging")
    _remove_stage_files(stage)
    paths = collect_sources(vault)
    _emit(progress_fn, {
        "phase": "scan", "current": 0, "total": len(paths), "sources": len(paths),
    })

    manifest: dict[str, str] = {}
    source_files: dict[str, Path] = {}
    redacted_sources = []
    failed_sources = []
    for path in paths:
        rel = path.relative_to(vault).as_posix()
        try:
            text, source_hash = _read_source(path)
        except (OSError, UnicodeError):
            failed_sources.append(rel)
            continue
        if _redacted(path, text):
            redacted_sources.append(rel)
            continue
        source_files[rel] = path
        manifest[rel] = source_hash
        _emit(progress_fn, {
            "phase": "scan", "current": len(source_files),
            "total": len(paths), "source": rel,
        })

    source_paths = sorted(manifest)
    base_report = {
        "sources": len(source_paths),
        "indexed_chunks": 0,
        "unchanged_sources": 0,
        "failed_chunks": 0,
        "failed_sources": sorted(failed_sources),
        "redacted_sources": sorted(redacted_sources),
        "path": str(target),
        "index_version": INDEX_VERSION,
        "retrieval_backend": "sqlite_fts5",
    }
    if failed_sources:
        _emit(progress_fn, {
            "phase": "complete", "sources": len(source_paths),
            "failed_sources": len(failed_sources), "status": "failed",
        })
        return base_report

    if target.exists() and not rebuild:
        try:
            with closing(_connect(target)) as conn:
                unchanged = _is_current_projection(
                    conn, manifest=manifest, chunk_size=chunk_size, overlap=overlap)
        except sqlite3.DatabaseError:
            unchanged = False
        if unchanged:
            base_report["unchanged_sources"] = len(source_paths)
            _emit(progress_fn, {
                "phase": "complete", "sources": len(source_paths),
                "unchanged_sources": len(source_paths), "status": "unchanged",
            })
            return base_report

    conn = None
    indexed = 0
    try:
        conn = _connect(stage)
        _ensure_schema(conn)
        _meta_set(conn, "source_index_version", INDEX_VERSION)
        _meta_set(conn, "retrieval_backend", "sqlite_fts5")
        _meta_set(conn, "chunk_size", str(chunk_size))
        _meta_set(conn, "overlap", str(overlap))
        conn.commit()
        conn.execute("BEGIN")
        for source_number, rel in enumerate(source_paths, start=1):
            text, observed_hash = _read_source(source_files[rel])
            if observed_hash != manifest[rel] or _redacted(source_files[rel], text):
                raise RuntimeError(f"source changed during build: {rel}")
            chunks = chunk_text(text, size=chunk_size, overlap=overlap)
            indexed += _insert_source(
                conn,
                source_path=rel,
                source_hash=manifest[rel],
                chunks=chunks,
                metadata=_source_metadata(text, rel),
            )
            _emit(progress_fn, {
                "phase": "index", "current": source_number,
                "total": len(source_paths), "indexed_chunks": indexed,
                "source": rel, "chunks": len(chunks),
            })
        conn.commit()
        conn.execute("INSERT INTO source_fts(source_fts) VALUES ('optimize')")
        conn.commit()
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("staged source index failed integrity check")
        conn.close()
        conn = None
        os.replace(stage, target)
        base_report["indexed_chunks"] = indexed
        _emit(progress_fn, {
            "phase": "complete", "sources": len(source_paths),
            "indexed_chunks": indexed, "status": "ok",
        })
        return base_report
    finally:
        if conn is not None:
            conn.close()
        _remove_stage_files(stage)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--progress", action="store_true",
                        help="emit progress events to stderr")
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    try:
        progress_fn = None
        if args.progress:
            progress_fn = lambda event: print(
                json.dumps({"progress": event}, sort_keys=True),
                file=sys.stderr, flush=True)
        report = build_source_index(
            vault, rebuild=args.rebuild, progress_fn=progress_fn)
        print(json.dumps(report, sort_keys=True))
        return 0 if not report["failed_sources"] else 1
    except Exception as exc:
        print(f"source-index: failed safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
