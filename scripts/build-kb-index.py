#!/usr/bin/env python3
"""Bouw/ververs kb-index.db uit de vault-markdown.

Hybride zoekindex (sqlite-vec + FTS5) over 02-wiki en 09-memory(current).
Afgeleid + herbouwbaar: --rebuild dropt de db en bouwt opnieuw uit files.
Hergebruikt de JSON embed-cache (emb.get_cached) zodat vectoren niet opnieuw
berekend worden. Toggle-gates: wiki onder embed_index, memory onder memory_capture.

Stdlib + sqlite-vec. Usage: python3 build-kb-index.py [--rebuild]
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _memory import read_status  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT = vault_root()
WIKI = VAULT / "02-wiki"
MEMORY = VAULT / "09-memory"
WIKI_SKIP = {"index.md", "log.md"}


def _doc_meta(path, layer):
    """(title, created, sources) uit één read; fail-soft naar leeg.

    sources = provenance-sleutels via _provenance.doc_sources (TASK-88):
    wiki-herkomstlinks c.q. memory source_session, geindexeerd zodat het
    coupling-signaal ze als één batch-query kan opvragen.
    """
    try:
        fm, body = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return "", "", ()
    try:
        import _provenance
        sources = tuple(_provenance.doc_sources(Path(path), layer, fm, body))
    except Exception:
        sources = ()
    return fm.get("title", ""), fm.get("created", ""), sources


def _collect():
    """(path, layer, status) voor elke te indexeren file, gated op toggles."""
    items = []
    if _settings.get("embed_index", True) and WIKI.exists():
        for f in sorted(WIKI.glob("**/*.md")):
            if f.name in WIKI_SKIP:
                continue
            items.append((f, "wiki", "current"))
    if _settings.get("memory_capture", True) and MEMORY.exists():
        for f in sorted(MEMORY.glob("**/*.md")):
            if read_status(f) == "current":
                items.append((f, "memory", "current"))
    return items


def main(rebuild: bool = False) -> None:
    eid = emb.embed_id()
    idx = _kbindex.index_path()

    # Niets te doen? Dan ook geen embed-probe. Die draaide onvoorwaardelijk vóór
    # de incrementele check, dus elke sessiestart betaalde een netwerkcall voor
    # een bouw die meestal niets doet. Alles hieronder is puur lokaal.
    if not rebuild and idx.exists():
        probe_conn = _kbindex.connect()
        try:
            has_meta = probe_conn.execute(
                "SELECT name FROM sqlite_master WHERE name='meta'").fetchone()
            fresh_enough = (_kbindex.is_valid_for(probe_conn, eid)
                            and _kbindex.meta_get(probe_conn, "unit_norm") == "1")
            if has_meta and fresh_enough:
                items = _collect()
                seen = {str(f) for f, _, _ in items}
                work = any(_kbindex.indexed_hash(probe_conn, str(f)) != emb.file_hash(f)
                           for f, _, _ in items)
                stale = probe_conn.execute(
                    "SELECT count(*) FROM docs").fetchone()[0] != len(seen)
                if not work and not stale:
                    print(f"kb-index: {len(seen)} files, 0 (re)indexed, "
                          f"{len(seen)} ongewijzigd, 0 verwijderd, 0 failed, backend={eid}")
                    return
        finally:
            probe_conn.close()

    # dim van het live model; faal-zacht als het model onbereikbaar is
    # Probe EERST: bij mislukking de bestaande index NIET wissen.
    probe = emb.embed("dimensie-probe")
    if not probe:
        print("kb-index: embedmodel onbereikbaar, overgeslagen", file=sys.stderr)
        return
    if rebuild and idx.exists():
        idx.unlink()
    conn = _kbindex.connect()
    dim = len(probe)
    # embed_id-mismatch => index ongeldig, verse start
    if idx != Path(":memory:") and conn.execute(
            "SELECT name FROM sqlite_master WHERE name='meta'").fetchone():
        # Ook herbouwen wanneer de unit_norm-vlag ontbreekt: een index van vóór
        # de normalisatie bevat ongenormaliseerde vectoren, waarvoor de
        # afstand-naar-cosinus-omrekening niet klopt. Eenmalig, en goedkoop --
        # de embeddings komen uit de cache, er wordt niets opnieuw geëmbed.
        if (not _kbindex.is_valid_for(conn, eid)
                or _kbindex.meta_get(conn, "unit_norm") != "1"):
            conn.close()
            if idx.exists():
                idx.unlink()
            conn = _kbindex.connect()
    _kbindex.ensure_schema(conn, dim=dim, embed_id=eid)
    _kbindex.set_unit_norm(conn, True)

    cache = emb.load_cache()
    seen = set()
    indexed = skipped = failed = 0
    for f, layer, status in _collect():
        sp = str(f)
        seen.add(sp)
        fh = emb.file_hash(f)
        if not rebuild and _kbindex.indexed_hash(conn, sp) == fh:
            skipped += 1
            continue
        vec = emb.get_cached(f, cache)
        if not vec:
            failed += 1
            continue
        title, created, sources = _doc_meta(f, layer)
        _kbindex.upsert(conn, path=sp, layer=layer, status=status,
                        body=emb.doc_text(f), vector=vec, file_hash=fh,
                        title=title, created=created, sources=sources)
        indexed += 1
    removed = _kbindex.prune(conn, keep_paths=seen)
    # De cache muteert alleen op het niet-overgeslagen pad; zonder nieuw
    # ingedexte bestanden is wegschrijven pure I/O.
    if indexed:
        emb.save_cache(cache)
    conn.close()
    print(f"kb-index: {len(seen)} files, {indexed} (re)indexed, {skipped} ongewijzigd, "
          f"{removed} verwijderd, {failed} failed, backend={eid}")


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv[1:]
    try:
        main(rebuild=rebuild)
    except Exception as e:
        print(f"kb-index: overgeslagen ({e})", file=sys.stderr)
