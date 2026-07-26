#!/usr/bin/env python3
"""_kbindex.py - lokale hybride zoekindex (sqlite-vec vec0 + FTS5).

Afgeleide, herbouwbare index over de vault-markdown. Markdown blijft bron van
waarheid; deze .db is een wegwerp-cache (rm + rebuild). Brute-force vec0 KNN +
FTS5 keyword. Dimensie komt van het live embedmodel (nooit gehardcode); embed_id
wordt opgeslagen zodat een modelwissel de index ongeldig maakt.

Pure functies: vectoren komen als argument binnen (geen embed-call hier), zodat
de module testbaar is zonder embedmodel. sqlite-vec is een pip-dep (gepind in
requirements.txt als sqlite-vec==0.1.9).

Stdlib + sqlite-vec.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

# Harde bovengrens van sqlite-vec: een vec0 KNN-query met k > 4096 gooit
# "OperationalError: k too large". Zie search().
VEC0_MAX_K = 4096


def index_path() -> Path:
    return vault_root() / ".claude" / "kb-index.db"


def connect(path=None) -> sqlite3.Connection:
    import sqlite_vec
    p = str(path) if path is not None else str(index_path())
    if path is None:
        index_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection, dim: int, embed_id: str) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS docs ("
        "doc_id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, "
        "layer TEXT, status TEXT, hash TEXT, title TEXT, created TEXT)")
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0("
        f"doc_id INTEGER PRIMARY KEY, embedding float[{int(dim)}])")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_docs USING fts5(body)")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('dim', ?)", (str(int(dim)),))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('embed_id', ?)", (embed_id,))
    conn.commit()


def meta_get(conn: sqlite3.Connection, key: str) -> "str | None":
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def is_valid_for(conn: sqlite3.Connection, embed_id: str) -> bool:
    return meta_get(conn, "embed_id") == embed_id


def set_unit_norm(conn: sqlite3.Connection, ok: bool) -> None:
    """Markeer of de opgeslagen vectoren genormaliseerd zijn.

    Off de hot path gezet, bij het bouwen van de index: search() leidt de
    cosinus af uit de L2-afstand en die omrekening geldt alleen voor
    eenheidsvectoren. Zonder deze vlag past search() geen drempel toe, zodat
    een index van vóór deze wijziging zich onveranderd gedraagt."""
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('unit_norm', ?)",
                 ("1" if ok else "0",))


def unit(vector):
    """Normaliseer naar lengte 1. Nulvector blijft ongewijzigd.

    Vectoren worden GENORMALISEERD opgeslagen, om twee redenen. Ten eerste
    ordent vec0 op L2-afstand; voor eenheidsvectoren is die ordening identiek
    aan cosinus-ordening, wat is wat een semantische zoek wil. Ten tweede geldt
    dan cos = 1 - d^2/2, zodat search() een echte relevantiedrempel kan
    toepassen zonder een tweede, dure SQL-aanroep.

    De embeddings zelf komen ongenormaliseerd binnen (_embeddings.cosine
    normaliseert daarom bij het vergelijken); normaliseren gebeurt hier, op de
    schrijfweg, niet op de leesweg.
    """
    vals = [float(x) for x in vector]
    norm = math.sqrt(sum(x * x for x in vals))
    if norm == 0.0:
        return vals
    return [x / norm for x in vals]


def _serialize(vector):
    from sqlite_vec import serialize_float32
    return serialize_float32(list(vector))


def indexed_hash(conn: sqlite3.Connection, path: str) -> "str | None":
    row = conn.execute("SELECT hash FROM docs WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM docs").fetchone()[0]


def upsert(conn: sqlite3.Connection, *, path: str, layer: str, status: str,
           body: str, vector, file_hash: str, title: str = "",
           created: str = "") -> int:
    """Insert/replace een doc over docs+fts_docs+vec_docs onder één doc_id."""
    row = conn.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
    if row:
        doc_id = row[0]
        conn.execute(
            "UPDATE docs SET layer=?, status=?, hash=?, title=?, created=? WHERE doc_id=?",
            (layer, status, file_hash, title, created, doc_id))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    else:
        cur = conn.execute(
            "INSERT INTO docs(path, layer, status, hash, title, created) "
            "VALUES (?,?,?,?,?,?)", (path, layer, status, file_hash, title, created))
        doc_id = cur.lastrowid
    conn.execute("INSERT INTO fts_docs(rowid, body) VALUES (?, ?)", (doc_id, body))
    conn.execute("INSERT INTO vec_docs(doc_id, embedding) VALUES (?, ?)",
                 (doc_id, _serialize(unit(vector))))
    conn.commit()
    return doc_id


def prune(conn: sqlite3.Connection, keep_paths: set) -> int:
    rows = conn.execute("SELECT doc_id, path FROM docs").fetchall()
    gone = [(d, p) for (d, p) in rows if p not in keep_paths]
    for doc_id, _ in gone:
        conn.execute("DELETE FROM docs WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM fts_docs WHERE rowid=?", (doc_id,))
        conn.execute("DELETE FROM vec_docs WHERE doc_id=?", (doc_id,))
    conn.commit()
    return len(gone)


def fts_expr(query_text: str) -> str:
    """FTS5 MATCH-expressie uit vrije tekst. Leeg = niets te zoeken.

    Eén bouwer voor zowel de poort (kb-recall.has_fts_match) als de ranking in
    search(). Die gebruikten verschillende expressies: search() gaf de RUWE
    prompt door, en FTS5 leest `?`, `/`, `+` en `"` als syntax. Het resultaat
    was een OperationalError die stil werd ingeslikt, waardoor de FTS-helft van
    de fusie bij precies de prompts wegviel die leestekens bevatten.

    Tokens van >= 4 tekens, ge-OR'd: stopwoorden en losse leestekens leveren
    geen vals signaal.
    """
    tokens = re.findall(r"[\w]{4,}", (query_text or "").lower())
    return " OR ".join(tokens)


def _cosine_from_l2(distance: float) -> float:
    """Cosinus uit de L2-afstand die vec0 al teruggeeft.

    Voor genormaliseerde vectoren geldt |a-b|^2 = 2 - 2*cos, dus
    cos = 1 - d^2/2. Dat is gratis: de afstand komt uit dezelfde KNN-query en
    werd tot nu toe weggegooid. Het alternatief -- vec_distance_cosine als
    aparte SQL-aanroep -- kost 118 ms per aanroep en tweemaal dat per prompt,
    op de weg die sub-seconde hoort te zijn.
    """
    return 1.0 - (distance * distance) / 2.0


def _rrf(rank_lists, k_const: int = 60) -> dict:
    """Reciprocal Rank Fusion: doc_id -> gefuseerde score (hoger = beter)."""
    scores: dict = {}
    for ranking in rank_lists:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k_const + rank)
    return scores


def search(conn: sqlite3.Connection, *, query_vector, query_text: str = "",
           k: int = 8, layers=None, statuses=("current",), min_cos: float = 0.0) -> list:
    """Hybride zoek: vec0 KNN + FTS5, gefuseerd met RRF.

    `min_cos` is een relevantie-ondergrens op de COSINUS, niet op de
    RRF-score -- die laatste is een rangnummer-artefact en zegt niets over
    inhoudelijke gelijkenis. De drempel geldt alleen wanneer de index als
    genormaliseerd is gemarkeerd (`meta['unit_norm']`); anders klopt de
    afstand-naar-cosinus-omrekening niet en houden we het bestaande gedrag.
    Een document dat door FTS gevonden is passeert altijd: een letterlijke
    trefwoordtreffer is een eigenstandig relevantiesignaal.
    """
    total = conn.execute("SELECT count(*) FROM docs").fetchone()[0]
    # vec0 accepteert maximaal k=4096; daarboven gooit de MATCH-query een
    # OperationalError die buiten de FTS-try valt en recall stil op [] zet.
    # De total-term blijft: die voorkomt layer-starvation (TASK-10).
    pool = min(max(k * 4, 20, total), VEC0_MAX_K)
    vec_rows = conn.execute(
        "SELECT doc_id, distance FROM vec_docs WHERE embedding MATCH ? "
        "ORDER BY distance LIMIT ?",
        (_serialize(unit(query_vector)), pool)).fetchall()
    vec_ranking = [r[0] for r in vec_rows]
    cos_by_id = {r[0]: _cosine_from_l2(r[1]) for r in vec_rows}
    rankings = [vec_ranking]
    fts_ids: set = set()
    expr = fts_expr(query_text)
    if expr:
        try:
            fts_ranking = [r[0] for r in conn.execute(
                "SELECT rowid FROM fts_docs WHERE fts_docs MATCH ? ORDER BY rank LIMIT ?",
                (expr, pool)).fetchall()]
            rankings.append(fts_ranking)
            fts_ids = set(fts_ranking)
        except sqlite3.OperationalError:
            pass  # FTS-syntaxfout (rare query) -> alleen vector
    fused = _rrf(rankings)
    if not fused:
        return []
    placeholders = ",".join("?" for _ in fused)
    meta = {r[0]: r for r in conn.execute(
        f"SELECT doc_id, path, layer, status, title, created FROM docs "
        f"WHERE doc_id IN ({placeholders})", tuple(fused)).fetchall()}
    # Alleen drempelen als de index expliciet genormaliseerd is; ontbreekt de
    # vlag (index van vóór deze wijziging) dan blijft het gedrag ongewijzigd
    # tot de eerstvolgende herbouw.
    gate = min_cos if (min_cos > 0.0 and meta_get(conn, "unit_norm") == "1") else 0.0
    out = []
    for doc_id, score in fused.items():
        row = meta.get(doc_id)
        if not row:
            continue
        _, path, layer, status, title, created = row
        if layers is not None and layer not in layers:
            continue
        if statuses is not None and status not in statuses:
            continue
        cos = cos_by_id.get(doc_id)
        by_fts = doc_id in fts_ids
        if gate and not by_fts and (cos is None or cos < gate):
            continue
        out.append({"path": path, "layer": layer, "status": status,
                    "title": title, "created": created, "score": score,
                    "cos": cos, "fts": by_fts})
    out.sort(key=lambda d: d["score"], reverse=True)
    # Afkappen NA het filteren: andersom zou een onder de drempel liggende
    # treffer een plek innemen die een geldige treffer had moeten krijgen.
    return out[:k]


# --- kennisgraaf in de index (TASK-71) --------------------------------------
#
# graph.json is inmiddels 4,2 MB. Dat bestand per prompt parsen past niet in
# het hot-path-budget van kb-retrieve (2,0s inclusief embed). Daarom leeft de
# graaf ook hier, als twee tabellen met indexen: "geef de buren van dit
# bestand" wordt dan een indexed lookup in plaats van een JSON-parse.
#
# Bewust GEEN voorberekende buurtabel. De buurvraag IS een query op
# graph_edges; een afgeleide tabel zou een tweede verouderingssignaal
# introduceren zonder eigen guard, en dat is precies de faalvorm die TASK-49
# voor .needs-rebuild documenteerde.
#
# Versheid heeft hier TWEE onafhankelijke assen. is_valid_for() bewaakt het
# embedding-model; de graaf kan verouderd zijn terwijl de embeddings vers zijn,
# of andersom. Vandaar een eigen vingerafdruk in meta. Een stale graaf degradeert
# naar GEEN buur, nooit naar een verkeerde buur.

#: contains-edges verbinden een documentnode met zijn eigen concepten (zie
#: graph-link-layer.py). Als buur-relatie zijn ze waardeloos: ze wijzen altijd
#: naar het bestand waar je al bent. Standaard dus uitgesloten.
GRAPH_SELF_RELATIONS = ("contains",)


def graph_index_path() -> Path:
    """De graaf woont in een EIGEN bestand, niet in kb-index.db.

    TASK-71 zette de graaftabellen in kb-index.db. Dat bestand wordt door
    build-kb-index.py in zijn geheel weggegooid -- `idx.unlink()` bij --rebuild
    en bij een embed_id- of unit_norm-mismatch. De graaf ging daar als bijvangst
    mee: waargenomen als `no such table: graph_nodes` na een herbouw, zonder dat
    iets dat meldde of herstelde.

    Een eigen bestand kost hier niets: graph_neighbors() bevraagt uitsluitend de
    graaftabellen op source_file en joint NIET met docs. Er is dus geen query die
    beide bestanden tegelijk nodig heeft. De alternatieven -- tabellen bewaren
    over een herbouw heen, of de bouwer erna opnieuw draaien -- laten de
    koppeling in stand en daarmee de kans dat iemand hem later opnieuw breekt.
    """
    return vault_root() / ".claude" / "kb-graph.db"


def graph_connect(path=None) -> sqlite3.Connection:
    """Verbinding met de graafindex.

    Bewust GEEN sqlite_vec: de graaftabellen zijn gewone SQL zonder vectoren.
    Dat scheelt niet alleen laadtijd, het maakt de graaf ook leesbaar op een
    machine waar de extensie ontbreekt -- bijvoorbeeld voor de statusregel bij
    de sessiestart, die alleen wil weten of de graaf actueel is.

    WAL, en dat is een bewuste keuze TEGEN de snelste optie. Deze index kan
    meerdere agents tegelijk bedienen (Claude, Codex en Copilot delen een vault)
    terwijl de achtergrondworker hem herbouwt.

    Gemeten, openen + een enkele meta-lookup, mediaan van 11 op de echte index:

        WAL       23,5 ms      DELETE   1,2 ms

    Dat verschil is echt: WAL legt per verse lezer een -shm-bestand aan, en dat
    is op Windows de hele kostenpost. Toch WAL, om twee redenen.

    Ten eerste: een race-proef met drie gelijktijdige lezers naast een schrijver
    die de graaf doorlopend herbouwde gaf in BEIDE modes nul geblokkeerde
    lezers, maar WAL haalde 93 schrijfrondes tegen 50 voor DELETE. WAL houdt
    lezers en schrijvers by design uit elkaar; DELETE leunt erop dat de
    busy-timeout het exclusieve commit-venster toevallig opvangt. Dat gaat goed
    tot een trage schijf of een grotere graaf dat venster oprekt.

    Ten tweede: die 23 ms staan tegenover een sessiestart van ~1230 ms. Op de
    plek waar de gebruiker het merkt is het ruis, en robuustheid onder
    gelijktijdig gebruik is dat niet.

    test_graafindex_gebruikt_wal legt deze keuze vast, zodat een latere
    snelheidsronde hem niet stilzwijgend terugdraait.
    """
    p = Path(path) if path is not None else graph_index_path()
    if path is None:
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_graph_schema(conn: sqlite3.Connection) -> None:
    """Maak de graaftabellen. Idempotent.

    Maakt ook een eigen `meta`-tabel aan, waarin de vingerafdruk van de graaf
    komt te staan. Sinds de graaf een eigen bestand heeft (zie graph_index_path)
    is dat niet dezelfde meta als die van de embedding-index, en dat is precies
    de bedoeling: de twee indexen hebben geen gedeelde staat meer en kunnen dus
    onafhankelijk herbouwd worden.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_nodes ("
        "id TEXT PRIMARY KEY, label TEXT, source_file TEXT, "
        "file_type TEXT, community INTEGER)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_edges ("
        "source TEXT, target TEXT, relation TEXT, confidence_score REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_src "
                 "ON graph_nodes(source_file)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source "
                 "ON graph_edges(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target "
                 "ON graph_edges(target)")
    conn.commit()


def graph_fingerprint(graph_path) -> str:
    """Goedkope vingerafdruk van graph.json: mtime + grootte.

    Bewust geen sha256: het bestand is megabytes groot en deze functie wordt
    ook op de leesweg aangeroepen om de versheid te toetsen. mtime+grootte
    verandert bij elke herbouw die de graaf echt wijzigt; een herbouw die
    byte-identieke inhoud oplevert hoeft ook niet opnieuw geladen te worden.
    """
    try:
        st = Path(graph_path).stat()
        return f"{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return ""


def set_graph_fingerprint(conn: sqlite3.Connection, fingerprint: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('graph_fingerprint', ?)",
                 (fingerprint,))
    conn.commit()


def graph_is_current(conn: sqlite3.Connection, graph_path) -> bool:
    """Komt de opgeslagen graaf overeen met graph.json op schijf?

    False bij een ontbrekend bestand, een ontbrekende vingerafdruk of een
    verschil. De leesweg gebruikt dit om te degraderen naar 'geen buur'.
    """
    fp = graph_fingerprint(graph_path)
    if not fp:
        return False
    try:
        return meta_get(conn, "graph_fingerprint") == fp
    except sqlite3.Error:
        # Index zonder meta-tabel (nooit gebouwd): geen graaf, dus geen buur.
        return False


def graph_count(conn: sqlite3.Connection) -> "tuple[int, int]":
    try:
        n = conn.execute("SELECT count(*) FROM graph_nodes").fetchone()[0]
        e = conn.execute("SELECT count(*) FROM graph_edges").fetchone()[0]
        return n, e
    except sqlite3.Error:
        return 0, 0


def replace_graph(conn: sqlite3.Connection, nodes, edges) -> "tuple[int, int]":
    """Vervang de hele graaf in één transactie.

    Vervangen in plaats van bijwerken: de graaf wordt als geheel herbouwd door
    graphify, dus een incrementele merge zou alleen maar een tweede plek zijn
    waar verouderde nodes kunnen achterblijven. Nodes zonder id worden
    overgeslagen; edges naar een onbekende node blijven staan (de query filtert
    ze vanzelf weg) zodat een halve graaf niet stil half verdwijnt.
    """
    ensure_graph_schema(conn)
    conn.execute("DELETE FROM graph_edges")
    conn.execute("DELETE FROM graph_nodes")
    node_rows = []
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        src = str(n.get("source_file") or "").replace("\\", "/")
        node_rows.append((str(nid), str(n.get("label") or ""), src,
                          str(n.get("file_type") or ""), n.get("community")))
    conn.executemany(
        "INSERT OR REPLACE INTO graph_nodes(id, label, source_file, file_type, community) "
        "VALUES (?, ?, ?, ?, ?)", node_rows)
    edge_rows = []
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s is None or t is None:
            continue
        try:
            score = float(e.get("confidence_score", 1.0))
        except (TypeError, ValueError):
            score = 1.0
        edge_rows.append((str(s), str(t), str(e.get("relation") or ""), score))
    conn.executemany(
        "INSERT INTO graph_edges(source, target, relation, confidence_score) "
        "VALUES (?, ?, ?, ?)", edge_rows)
    conn.commit()
    return len(node_rows), len(edge_rows)


def graph_neighbors(conn: sqlite3.Connection, source_file: str, *, limit: int = 5,
                    min_confidence: float = 0.0,
                    exclude_relations=GRAPH_SELF_RELATIONS) -> list:
    """Bestanden die via de graaf aan source_file grenzen, gewogen.

    Werkt op BESTANDSNIVEAU, niet op conceptniveau: alle nodes van het
    bronbestand vormen samen het startpunt, en de buren worden weer naar hun
    bronbestand teruggerekend en opgeteld. Zo telt een bestand dat via drie
    concepten verbonden is zwaarder dan een dat via één verbinding hangt.

    Ongericht: een edge telt in beide richtingen. De graaf is als undirected
    gebouwd (build_from_json zonder --directed), dus richting zou hier een
    betekenis suggereren die de data niet draagt.

    Geeft [{"source_file": ..., "weight": float, "hops": int}], aflopend op
    gewicht, met een deterministische tie-break op pad.
    """
    src = str(source_file or "").replace("\\", "/")
    if not src:
        return []
    excl = tuple(exclude_relations or ())
    placeholders = ",".join("?" for _ in excl)
    rel_filter = f"AND e.relation NOT IN ({placeholders})" if excl else ""
    sql = f"""
        SELECT n2.source_file AS nbr, sum(e.confidence_score) AS w, count(*) AS hops
        FROM graph_nodes n1
        JOIN graph_edges e
          ON (e.source = n1.id OR e.target = n1.id)
        JOIN graph_nodes n2
          ON n2.id = CASE WHEN e.source = n1.id THEN e.target ELSE e.source END
        WHERE n1.source_file = ?
          AND n2.source_file <> ''
          AND n2.source_file <> n1.source_file
          AND e.confidence_score >= ?
          {rel_filter}
        GROUP BY n2.source_file
        ORDER BY w DESC, nbr ASC
        LIMIT ?
    """
    params = [src, float(min_confidence), *excl, int(limit)]
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []
    return [{"source_file": r[0], "weight": float(r[1]), "hops": int(r[2])} for r in rows]
