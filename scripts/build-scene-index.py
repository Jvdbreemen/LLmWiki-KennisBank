#!/usr/bin/env python3
"""build-scene-index.py - build the derived L2 scene layer (kb-scene.db).

Reads current memory documents and their stored embeddings from kb-index.db,
groups them with the selected clusterer, and writes scenes plus normalised
centroids. Off the hot path, and it issues NO embedding call: every vector it
needs is already in the index.

Usage:
    python3 build-scene-index.py [--clusterer community|tags|llm] [--json]

See docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md (TASK-134).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _kbindex  # noqa: E402
import _scenes  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def _read_only(path, *, vec0: bool = False) -> sqlite3.Connection:
    """Open a database read-only; the builder never writes to index or graph.

    ``vec0=True`` also loads the sqlite-vec extension. kb-index.db stores its
    embeddings in a vec0 virtual table, so even a plain SELECT over vec_docs
    fails with "no such module: vec0" without it. kb-graph.db is ordinary
    SQLite and needs nothing.
    """
    uri = "file:" + str(path).replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    if vec0:
        conn.enable_load_extension(True)
        conn.load_extension(_kbindex.vec0_extension())
        conn.enable_load_extension(False)
    return conn


def memory_vectors(index_conn) -> dict:
    """{path: vector} for every current memory doc in the index.

    Reads the stored float32 blobs straight out of vec_docs. That is the whole
    reason scenes are cheap: the embedding work was already paid for at index
    build time, so clustering costs no model call at all.
    """
    out = {}
    rows = index_conn.execute(
        "SELECT d.path, v.embedding FROM docs d JOIN vec_docs v ON v.doc_id = d.doc_id "
        "WHERE d.layer='memory' AND d.status='current'").fetchall()
    for path, blob in rows:
        try:
            out[str(path).replace("\\", "/")] = _scenes.deserialize(blob)
        except Exception:
            continue
    return out


def memory_meta(paths) -> dict:
    """{path: {"tags": [...], "created": "...", "title": "..."}} from frontmatter."""
    from _frontmatter import parse_frontmatter
    root = vault_root()
    out = {}
    for p in paths:
        entry = {"tags": [], "created": "", "title": Path(p).stem}
        try:
            text = (root / p).read_text(encoding="utf-8", errors="replace")
            fm, _ = parse_frontmatter(text)
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip().strip('"\'') for t in tags.strip("[]").split(",")
                        if t.strip()]
            entry["tags"] = [str(t) for t in tags if str(t).strip()]
            entry["created"] = str(fm.get("created", ""))
            entry["title"] = str(fm.get("title", "") or Path(p).stem)
        except Exception:
            pass
        out[p] = entry
    return out


def relative_key(path) -> str:
    """Vault-relative form of an indexed path.

    kb-index.db stores ABSOLUTE paths; kb-graph.db stores VAULT-RELATIVE ones
    ("09-memory/x.md"). Comparing the two forms directly silently matches
    nothing -- 1428 memories in, zero scenes out, no error anywhere. This repo
    has been bitten by exactly this mismatch before, so the conversion lives in
    one named function with a regression test rather than inline.
    """
    s = str(path).replace("\\", "/")
    root = str(vault_root()).replace("\\", "/").rstrip("/")
    if root and s.startswith(root + "/"):
        return s[len(root) + 1:]
    return s


def build(clusterer: str, index_conn, graph_conn, scene_conn) -> dict:
    """Cluster the memory layer and write scenes + centroids. Returns stats.

    Clustering runs on vault-relative keys (what the graph and frontmatter
    speak); scenes are WRITTEN with the absolute paths the index and the recall
    path use, so a member lookup at query time compares like with like.
    """
    vectors = memory_vectors(index_conn)
    rel_to_abs = {}
    for abs_path in sorted(vectors):
        rel_to_abs.setdefault(relative_key(abs_path), abs_path)
    rel_paths = sorted(rel_to_abs)

    if clusterer == "community":
        groups = _scenes.cluster_community(rel_paths, graph_conn)
    elif clusterer == "tags":
        groups = _scenes.cluster_tags(memory_meta(rel_paths))
    elif clusterer == "llm":
        import _llm
        groups = _scenes.cluster_llm(memory_meta(rel_paths), llm_fn=_llm.generate,
                                     max_scenes=15)
    else:
        raise SystemExit(f"unknown clusterer: {clusterer}")

    scenes = []
    members = 0
    skipped = 0
    for label, group in sorted(groups.items()):
        abs_group = [rel_to_abs[p] for p in group if p in rel_to_abs]
        vecs = [vectors[p] for p in abs_group]
        if not vecs:
            skipped += 1
            continue
        scenes.append((label, abs_group, _scenes.centroid(vecs)))
        members += len(abs_group)
    n = _scenes.write_scenes(scene_conn, clusterer, scenes)
    return {"scenes": n, "members": members, "skipped": skipped,
            "memories": len(vectors)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="build kb-scene.db")
    ap.add_argument("--clusterer", default="community", choices=_scenes.CLUSTERERS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    index_path = _kbindex.index_path()
    if not Path(index_path).exists():
        print("kb-index.db not found; run build-kb-index.py first", file=sys.stderr)
        return 1
    index_conn = _read_only(index_path, vec0=True)
    graph_conn = (_read_only(_kbindex.graph_index_path())
                  if Path(_kbindex.graph_index_path()).exists() else None)
    scene_conn = _scenes.connect()
    try:
        stats = build(args.clusterer, index_conn, graph_conn, scene_conn)
        _scenes.set_fingerprint(scene_conn, _scenes.fingerprint(index_path))
    finally:
        for c in (index_conn, graph_conn, scene_conn):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
    stats["clusterer"] = args.clusterer
    if args.json:
        print(json.dumps(stats, ensure_ascii=False))
    else:
        print(f"scenes: {stats['scenes']}  members: {stats['members']}"
              f"/{stats['memories']}  clusterer: {args.clusterer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
