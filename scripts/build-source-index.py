#!/usr/bin/env python3
"""Build the isolated, disposable raw-source projection."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _source_recall as source  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402


APPROVED_ROOTS = source.APPROVED_ROOTS
TEXT_EXTENSIONS = source.TEXT_EXTENSIONS
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_OVERLAP = 200
INDEX_VERSION = "source-index-v1"


def collect_sources(vault: Path) -> list[Path]:
    paths = []
    for root in APPROVED_ROOTS:
        directory = vault / root
        if not directory.is_dir():
            continue
        paths.extend(path for path in directory.rglob("*")
                     if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS)
    return sorted(set(paths), key=lambda path: path.as_posix())


def _manifest(conn) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT source_path, source_hash FROM source_manifest").fetchall()
    except Exception:
        return {}
    return {str(path): str(file_hash) for path, file_hash in rows}


def _ensure_manifest(conn) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS source_manifest ("
                 "source_path TEXT PRIMARY KEY, source_hash TEXT NOT NULL)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _redacted(path: Path, text: str) -> bool:
    if ".redacted." in path.name.lower() or path.name.lower().endswith(".redacted"):
        return True
    header = text[:4000].lower()
    return "redacted:" in header and any(token in header for token in
                                         ("redacted: true", "redacted: yes", "redacted: 1"))


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


def _emit(progress_fn, event: dict) -> None:
    """Progress is diagnostic only; a broken reporter must not break a build."""
    if progress_fn is None:
        return
    try:
        progress_fn(dict(event))
    except Exception:
        pass


def build_source_index(vault: Path, *, rebuild: bool = False, embed_fn=None,
                       embed_id: str = "", chunk_size: int = DEFAULT_CHUNK_SIZE,
                       overlap: int = DEFAULT_OVERLAP, progress_fn=None) -> dict:
    vault = Path(vault)
    target = vault / ".claude" / "kb-source.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = collect_sources(vault)
    _emit(progress_fn, {"phase": "scan", "current": 0, "total": len(paths),
                        "sources": len(paths)})
    manifest = {}
    texts = {}
    redacted_sources = []
    failed_sources = []
    for path in paths:
        rel = path.relative_to(vault).as_posix()
        try:
            text = _read(path)
        except (OSError, UnicodeError):
            failed_sources.append(rel)
            continue
        if _redacted(path, text):
            redacted_sources.append(rel)
            continue
        texts[rel] = text
        manifest[rel] = source.sha256_file(path)
        _emit(progress_fn, {"phase": "scan", "current": len(texts),
                            "total": len(paths), "source": rel})
    paths = [vault / rel for rel in sorted(manifest)]
    base_report = {"sources": len(paths), "indexed_chunks": 0,
                   "unchanged_sources": 0, "failed_chunks": 0,
                   "failed_sources": sorted(failed_sources),
                   "redacted_sources": sorted(redacted_sources),
                   "path": str(target), "index_version": INDEX_VERSION}
    if failed_sources:
        _emit(progress_fn, {"phase": "complete", "sources": len(paths),
                            "failed_sources": len(failed_sources), "status": "failed"})
        return base_report
    existing = {}
    if target.exists() and not rebuild:
        conn = source.connect(target)
        try:
            existing = _manifest(conn)
            current_embed_id = source._kbindex.meta_get(conn, "embed_id")
            current_version = source._kbindex.meta_get(conn, "source_index_version")
        finally:
            conn.close()
        if (existing == manifest and current_embed_id == embed_id
                and current_version == INDEX_VERSION):
            base_report["unchanged_sources"] = len(paths)
            _emit(progress_fn, {"phase": "complete", "sources": len(paths),
                                "unchanged_sources": len(paths), "status": "unchanged"})
            return base_report

    stage = target.with_name(target.name + ".staging")
    if stage.exists():
        stage.unlink()
    conn = None
    indexed = unchanged = failed = 0
    try:
        # The first successful vector determines the schema dimension.  No
        # production file is replaced until every vector and write succeeds.
        dimension = None
        conn = None
        for path in paths:
            rel = path.relative_to(vault).as_posix()
            text = texts[rel]
            chunks = source.chunk_text(text, size=chunk_size, overlap=overlap)
            vectors = []
            for chunk in chunks:
                try:
                    vector = embed_fn(chunk["text"]) if embed_fn else None
                except Exception:
                    vector = None
                if vector is None:
                    failed += 1
                elif dimension is None:
                    dimension = len(vector)
                elif len(vector) != dimension:
                    failed += 1
                    vector = None
                vectors.append(vector)
            if any(vector is None for vector in vectors):
                continue
            if conn is None:
                if dimension is None:
                    continue
                conn = source.connect(stage)
                source.ensure_schema(conn, dimension, embed_id)
                _ensure_manifest(conn)
                source._kbindex.meta_set(conn, "source_index_version", INDEX_VERSION)
            source.upsert_source(
                conn, source_path=rel, source_hash=manifest[rel], chunks=chunks,
                vectors=vectors, metadata=_source_metadata(text, rel))
            conn.execute("INSERT OR REPLACE INTO source_manifest(source_path, source_hash) VALUES (?,?)",
                         (rel, manifest[rel]))
            conn.commit()
            indexed += len(chunks)
            _emit(progress_fn, {"phase": "index", "current": indexed,
                                "total": sum(len(source.chunk_text(texts[item], size=chunk_size,
                                                                     overlap=overlap))
                                               for item in texts),
                                "source": rel, "chunks": len(chunks)})
        if failed:
            base_report.update({"indexed_chunks": indexed, "unchanged_sources": unchanged,
                                "failed_chunks": failed})
            _emit(progress_fn, {"phase": "complete", "sources": len(paths),
                                "indexed_chunks": indexed, "failed_chunks": failed,
                                "status": "failed"})
            return base_report
        if conn is None:
            # Empty corpora still produce no replacement: there is no useful
            # vector dimension and therefore no valid searchable projection.
            base_report["unchanged_sources"] = len(paths)
            _emit(progress_fn, {"phase": "complete", "sources": len(paths),
                                "unchanged_sources": len(paths), "status": "empty"})
            return base_report
        conn.close()
        conn = None
        os.replace(stage, target)
        base_report.update({"indexed_chunks": indexed, "unchanged_sources": unchanged})
        _emit(progress_fn, {"phase": "complete", "sources": len(paths),
                            "indexed_chunks": indexed, "status": "ok"})
        return base_report
    finally:
        if conn is not None:
            conn.close()
        if stage.exists():
            stage.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--progress", action="store_true",
                        help="emit progress events to stderr")
    args = parser.parse_args(argv)
    vault = args.vault or Path(os.environ.get("KENNISBANK_VAULT", "."))
    try:
        import _embeddings as emb
        _prov, _model, endpoint, _key = emb._resolve()
        if not emb.endpoint_allowed(emb.provider(), endpoint):
            return 2
        progress_fn = None
        if args.progress:
            progress_fn = lambda event: print(
                json.dumps({"progress": event}, sort_keys=True),
                file=sys.stderr, flush=True)
        report = build_source_index(vault, rebuild=args.rebuild,
                                    embed_fn=lambda text: emb.embed(text, kind="doc"),
                                    embed_id=emb.embed_id(), progress_fn=progress_fn)
        print(json.dumps(report, sort_keys=True))
        return 0 if not report["failed_chunks"] else 1
    except Exception as exc:
        print(f"source-index: failed safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
