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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _settings  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _memory import read_status  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

VAULT = vault_root()
WIKI = VAULT / "02-wiki"
MEMORY = VAULT / "09-memory"
WIKI_SKIP = {"index.md", "log.md"}

#: How much of a document reaches the FTS index. Deliberately NOT the embedding
#: cap, which is what it used to share.
#:
#: `doc_text` caps at 4000 characters because the embedding model runs at
#: num_ctx=2048 -- a setting chosen to free 2.18 GB of VRAM, and above which the
#: embed call does not truncate but FAILS. That constraint is real and belongs
#: to the vector arm alone. FTS5 has no context window; it was paying an
#: embedding model's limit for no reason.
#:
#: The cost of the whole corpus is under a megabyte of text, and the search is
#: hybrid (vec0 KNN + FTS5 fused by RRF), so this gives the lexical arm sight of
#: material the vector arm structurally cannot reach: 72 of 206 articles run
#: past 4000 characters and 16.6% of all wiki text sat beyond it (TASK-164).
FTS_BODY_CAP = 200_000


def _fts_len_mismatch(conn, sp, f) -> bool:
    """Stored FTS row length vs what doc_text would store under the CURRENT
    cap. Self-truing: it recomputes the expectation, so it also repairs a
    legacy row whose cap was never stamped, in either direction of a cap
    change (TASK-186)."""
    row = conn.execute(
        "SELECT length(body) FROM fts_docs WHERE rowid="
        "(SELECT doc_id FROM docs WHERE path=?)", (sp,)).fetchone()
    stored = row[0] if row and row[0] is not None else -1
    return stored != len(emb.doc_text(f, cap=FTS_BODY_CAP))


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


def _active_layers() -> set:
    """Lagen die deze run daadwerkelijk inleest.

    Los van _collect() omdat de prune-stap dit óók moet weten: een laag die niet
    is ingelezen heeft een lege keep-set, en zonder deze verzameling leest prune
    dat als "alles verwijderd". Zie _kbindex.prune (TASK-136).

    Een uitgezette toggle betekent "indexeer niets nieuws uit deze laag", niet
    "beschouw deze laag als verdwenen".
    """
    layers = set()
    if _settings.get("embed_index", True) and WIKI.exists():
        layers.add("wiki")
    if _settings.get("memory_capture", True) and MEMORY.exists():
        layers.add("memory")
    return layers


#: Boven welk aandeel van de index een verwijdering een expliciete melding krijgt.
PRUNE_NOTICE_FRACTION = 0.10


def prune_notice(removed: int, total_before: int, layers) -> str:
    """Melding voor een bouw die een flink deel van de index weggooit, of "".

    Een verwijdering stond alleen als getal in de slotregel, tussen vier andere
    getallen. Zo verdwenen eerst 199 wiki- en daarna 1508 memory-documenten
    zonder dat iemand het zag: de regel meldde het, maar meldde het als routine.
    Boven een tiende van de index is het geen routine (TASK-136).
    """
    if not removed or not total_before:
        return ""
    if removed <= total_before * PRUNE_NOTICE_FRACTION:
        return ""
    namen = ", ".join(sorted(layers)) or "geen"
    return (f"kb-index: LET OP -- {removed} van {total_before} documenten verwijderd "
            f"({100 * removed / total_before:.0f}%). Lagen in deze run: {namen}.")


def _collect():
    """(path, layer, status) voor elke te indexeren file, gated op toggles."""
    items = []
    active = _active_layers()
    if "wiki" in active:
        for f in sorted(WIKI.glob("**/*.md")):
            if f.name in WIKI_SKIP:
                continue
            items.append((f, "wiki", "current"))
    if "memory" in active:
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
                            and _kbindex.meta_get(probe_conn, "unit_norm") == "1"
                            # A cap change alters what indexed FTS rows should
                            # contain; without this stamp the fast path kept
                            # every truncated row forever (TASK-186).
                            and _kbindex.meta_get(probe_conn, "fts_body_cap")
                            == str(FTS_BODY_CAP))
            if has_meta and fresh_enough:
                items = _collect()
                seen = {str(f) for f, _, _ in items}
                work = any(_kbindex.indexed_hash(probe_conn, str(f)) != emb.file_hash(f)
                           for f, _, _ in items)
                # Tel alleen de lagen die deze run inleest. Met een uitgezette
                # toggle staat de bevroren laag wél in docs maar niet in seen,
                # en dan is deze check altijd "stale" -- dus draait elke
                # sessiestart een volledige pas voor niets (TASK-136).
                active = _active_layers()
                qmarks = ",".join("?" for _ in active) or "''"
                counted = probe_conn.execute(
                    f"SELECT count(*) FROM docs WHERE layer IN ({qmarks})",
                    tuple(sorted(active))).fetchone()[0]
                stale = counted != len(seen)
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
        # One line, but a complete one: name the backend and the remedy. The
        # bare "onbereikbaar" hid the difference between Ollama-down and
        # model-never-pulled for weeks after the default flip (TASK-182).
        print(f"kb-index: embed-backend {eid} gaf geen vector (model niet "
              f"gepulled of Ollama down); bestaande index blijft staan. "
              f"Herstel: ollama pull <model> en draai met --rebuild",
              file=sys.stderr)
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
    failed_docs = []
    # Cap changed since this index was stamped? Then hash-matched rows may
    # hold truncated FTS bodies; repair exactly those (targeted, from the
    # embedding cache - no re-embedding) instead of a 10-minute full rebuild.
    fts_refresh = _kbindex.meta_get(conn, "fts_body_cap") != str(FTS_BODY_CAP)
    # _collect() is een generator; hier eerst uitputten zodat het totaal
    # bekend is. Een percentage zonder noemer is geen percentage, en de lijst
    # met paden weegt niets naast de embeddings die erachteraan komen.
    docs = list(_collect())
    with Progress(len(docs), "index bijwerken") as p:
        for f, layer, status in docs:
            p.step()
            sp = str(f)
            seen.add(sp)
            fh = emb.file_hash(f)
            if not rebuild and _kbindex.indexed_hash(conn, sp) == fh:
                if not (fts_refresh and _fts_len_mismatch(conn, sp, f)):
                    skipped += 1
                    continue
            vec = emb.get_cached(f, cache)
            if not vec:
                failed += 1
                failed_docs.append(sp)
                continue
            title, created, sources = _doc_meta(f, layer)
            _kbindex.upsert(conn, path=sp, layer=layer, status=status,
                            body=emb.doc_text(f, cap=FTS_BODY_CAP),
                            vector=vec, file_hash=fh,
                            title=title, created=created, sources=sources)
            indexed += 1
    if failed_docs:
        # By name: an aggregate count hid WHICH documents silently dropped
        # out of both index arms (TASK-186). Wording hedges on the cause -
        # only the ollama backend hard-fails past num_ctx; cloud backends
        # truncate server-side.
        rels = [os.path.relpath(p, VAULT) for p in failed_docs]
        print(f"kb-index: geen embedding voor {len(rels)} document(en): "
              f"{', '.join(rels)} (model-fout, of het document tokeniseert "
              f"voorbij num_ctx={emb.OLLAMA_NUM_CTX}; zie _embeddings.EMBED_DOC_CAP)",
              file=sys.stderr)
    # Stamp AFTER the corrective pass: written only when the pass completed,
    # so a killed run rescans next time. Deliberately not gated on failed==0 -
    # one permanently failing doc must not force the length scan forever; the
    # by-name report above keeps that residue visible.
    _kbindex.meta_set(conn, "fts_body_cap", str(FTS_BODY_CAP))
    total_before = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
    removed = _kbindex.prune(conn, keep_paths=seen, layers=_active_layers())
    notice = prune_notice(removed, total_before, _active_layers())
    if notice:
        print(notice, file=sys.stderr)
    # De cache muteert alleen op het niet-overgeslagen pad; zonder nieuw
    # ingedexte bestanden is wegschrijven pure I/O.
    # Zie build-embed-index: een text_hash-migratie is aan de entry niet te zien,
    # dus zonder emb.migrated() landt hij nooit op schijf.
    if indexed or emb.migrated():
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
