#!/usr/bin/env python3
"""_maintenance.py - deterministische cross-memory-primitieven (supersede/cluster).

Levert de bouwstenen voor de onderhoudspas: laad current-memories met hun vectoren,
vind hoog-cosine paren (supersede-kandidaten), en tel verwante buren (cluster-
promotie). Geen LLM hier - dat zit in de seams (_judge / judge_supersede). De
vector-bron is injecteerbaar zodat de plumbing zonder model getest wordt.

Stdlib + _embeddings.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _llmjson  # noqa: E402
from _frontmatter import parse_frontmatter, split_frontmatter  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def _index_vectors() -> dict:
    """path -> (file_hash, vector) for the memory layer out of kb-index.db.

    Fail-soft and best-effort: a missing index, a missing sqlite-vec extension
    or a schema that does not match simply yields {}, and every caller falls
    back to the embedding cache. This is a shortcut, never a dependency.

    Reuses _index_conn's gate (embed_id AND unit_norm) instead of a private
    copy of half of it, and returns the stored file hash next to the vector:
    the index lags the filesystem by design after every sweep, and serving a
    stale vector for an edited memory meant judging it with the embedding of
    its PREVIOUS content (TASK-191). Callers must verify the hash.
    """
    conn = _index_conn()
    if conn is None:
        return {}
    try:
        import array
        out = {}
        for path, fhash, blob in conn.execute(
                "SELECT d.path, d.hash, v.embedding FROM docs d "
                "JOIN vec_docs v ON v.doc_id = d.doc_id WHERE d.layer='memory'"):
            a = array.array("f")
            a.frombytes(blob)
            out[str(path)] = (fhash, list(a))
        return out
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _index_conn():
    """A read-only connection to kb-index.db, or None when it is not usable.

    Same contract as _index_vectors: a missing index, a missing sqlite-vec
    extension or a different embed_id yields None and the caller falls back.
    Comparing vectors across two embedding spaces is silently meaningless, so
    the embed_id check is a gate and not a hint.
    """
    conn = None
    try:
        import sqlite3
        import sqlite_vec
        db = vault_root() / ".claude" / "kb-index.db"
        if not db.exists():
            return None
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1.0)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        row = conn.execute("SELECT value FROM meta WHERE key='embed_id'").fetchone()
        if not row or row[0] != emb.embed_id():
            conn.close()
            return None
        if _kbindex().meta_get(conn, "unit_norm") != "1":
            # Without normalised vectors the distance-to-cosine conversion is
            # wrong, and a wrong cosine here decides whether memories get
            # closed. Fall back rather than guess.
            conn.close()
            return None
        return conn
    except Exception:
        # Every early return above closes deliberately; this one catches the
        # rest -- a missing meta table, a failed extension load, a schema that
        # does not match. Without it the handle stays open on every fallback,
        # and the sweep takes this path on every run when the index is stale.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None


def _kbindex():
    import _kbindex as m
    return m


#: Where the neighbour search starts. Measured on the live vault, no memory has
#: more than three neighbours above 0.75, so 32 is enormous headroom -- but the
#: number is a starting point, not a cap: see _neighbours_from_index.
INDEX_PROBE_K = 32
#: Hard ceiling on the widening loop, matching what vec0 itself accepts.
INDEX_MAX_K = 4096


def _neighbours_from_index(items: list, threshold: float, conn=None):
    """{path -> [(other_path, cosine), ...]} for every pair above threshold.

    Returns None when the index cannot answer, so the caller keeps the
    brute-force path. That path stays; this is a shortcut, never a dependency.

    Why this is EXACT and not an approximation. vec0 returns rows ordered by
    distance, and for unit vectors distance and cosine are monotonically
    related. So if the k-th row already sits below the threshold, no row beyond
    k can sit above it -- the answer is provably complete. Only when the whole
    window is still above the threshold is anything possibly missing, and then
    k widens. A fixed k would be a silent truncation, which is precisely the
    class of bug this codebase has been removing all week.

    The index holds every layer, not just memory, so the window is filtered
    down to the caller's own item set afterwards. That is also why the window
    has to be able to grow: a memory whose nearest neighbours are all wiki
    articles would otherwise come back empty.
    """
    own = conn is None
    if own:
        conn = _index_conn()
    if conn is None:
        return None
    kbi = _kbindex()
    try:
        by_path = {it["path"]: it for it in items}
        doc_ids = {}
        for doc_id, path in conn.execute("SELECT doc_id, path FROM docs"):
            doc_ids[doc_id] = str(path)
        indexed = set(doc_ids.values())
        out = {p: [] for p in by_path}

        # Een memory die de index nog niet kent, kan er ook niet uit komen. Dat
        # is niet zeldzaam maar de normale toestand vlak na een sweep: die
        # schrijft memories, de index loopt erachteraan. Twee ONGEINDEXEERDE
        # memories zouden elkaar dus nooit vinden, en dat zou een stille
        # onvolledigheid zijn -- precies wat een index-kortsluiting NIET mag
        # kosten.
        #
        # Daarom een hybride: de index beantwoordt de vraag voor wat hij kent,
        # en wat hij niet kent wordt tegen alles uitgerekend. Dat laatste is
        # O(ongeindexeerd x alles), dus goedkoop zolang de achterstand klein is,
        # en het antwoord is exact ongeacht hoe ver de index achterloopt.
        onbekend = [it for it in items if it["path"] not in indexed]
        if onbekend:
            with Progress(len(onbekend),
                          f"{len(onbekend)} nog niet geindexeerd, los vergelijken") as p:
                for a in onbekend:
                    p.step()
                    for b in items:
                        if a["path"] == b["path"]:
                            continue
                        s = emb.cosine(a["vec"], b["vec"])
                        if s > threshold:
                            out[a["path"]].append((b["path"], s))
                            out[b["path"]].append((a["path"], s))

        with Progress(len(items), f"neighbours above {threshold} (index)") as p:
            for it in items:
                p.step()
                if it["path"] not in indexed:
                    continue  # hierboven al exact afgehandeld
                k = INDEX_PROBE_K
                while True:
                    rows = conn.execute(
                        "SELECT doc_id, distance FROM vec_docs "
                        "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                        (kbi._serialize(kbi.unit(it["vec"])), k)).fetchall()
                    if not rows:
                        break
                    last_cos = kbi._cosine_from_l2(rows[-1][1])
                    # Complete when the window has run out of candidates or its
                    # far edge already falls below the threshold.
                    if len(rows) < k or last_cos <= threshold or k >= INDEX_MAX_K:
                        break
                    k = min(k * 4, INDEX_MAX_K)
                for doc_id, distance in rows:
                    other = doc_ids.get(doc_id)
                    if other is None or other == it["path"] or other not in by_path:
                        continue
                    cos = kbi._cosine_from_l2(distance)
                    if cos > threshold:
                        out[it["path"]].append((other, cos))
        # Dedup: de losse tak schrijft beide richtingen, en de index kan een
        # paar ook al gemeld hebben. Een dubbel geteld paar zou neighbor_counts
        # laten liegen.
        for path, buren in out.items():
            gezien, uniek = set(), []
            for other, cos in buren:
                if other in gezien:
                    continue
                gezien.add(other)
                uniek.append((other, cos))
            out[path] = uniek
        return out
    except Exception:
        return None
    finally:
        if own:
            try:
                conn.close()
            except Exception:
                pass


def current_items(get_cached_fn=None, statuses=("current",)) -> list:
    """Laad memories uit 09-memory/ met hun embeddings, gefilterd op status.

    Returns een list[dict] met sleutels: path, title, created, valid_from,
    body, vec. Items zonder vector worden overgeslagen.

    Args:
        get_cached_fn: optionele injectable get_cached(path, cache, recompute=True)
                       om de echte emb.get_cached te vervangen in tests.
        statuses: welke status-waarden meedoen (default alleen "current";
                  de write-time reconcile gebruikt ("current", "unverified")).
    """
    import _memory
    gc = get_cached_fn or (lambda p, cache, recompute=True: emb.get_cached(p, cache))
    cache = emb.load_cache()
    # De index is de goedkope bron voor precies deze vectoren. Zonder deze stap
    # valt elke memory terug op get_cached(), en die embedt opnieuw zodra het
    # embed_id van de cache-entry niet matcht. Gemeten op de live vault: 1506 van
    # 1531 cache-entries stonden onder een ouder embed_id, dus elke pass die
    # current_items() aanroept -- supersede_pass, cluster_promote_pass en de
    # reconcile-pool -- wilde de hele corpus opnieuw embedden. Een handmatige
    # aanroep draaide na tien minuten nog. De index bevat wel de juiste vectoren
    # (embed_id ollama:qwen3-embedding:4b, 1531 memory-docs), want die wordt
    # incrementeel bijgewerkt door build-kb-index (TASK-148).
    from_index = _index_vectors()
    mdir = vault_root() / "09-memory"
    out = []
    if not mdir.exists():
        return out
    files = sorted(mdir.glob("**/*.md"))
    # Zichtbaar maken hoeveel er UIT DE INDEX komt en hoeveel er alsnog
    # geembed moet worden: het verschil tussen zestien seconden en tien
    # minuten zit precies daar (TASK-148), en zonder deze melding ziet een
    # trage run er hetzelfde uit als een snelle die vastloopt.
    embedded = 0
    with Progress(len(files), "memories inlezen") as p:
        for f in files:
            p.step()
            try:
                raw = f.read_bytes()
                fm, body = parse_frontmatter(raw.decode("utf-8"))
            except Exception:
                continue
            if fm.get("status") not in statuses:
                continue
            # The index vector counts only when its stored hash matches the
            # file AS IT IS NOW: the index lags the filesystem by design, and
            # an edited memory served its previous content's embedding to the
            # very passes that close memories (TASK-191).
            entry = from_index.get(str(f))
            vec = None
            if entry and entry[0] == emb.bytes_hash(raw):
                vec = entry[1]
            if not vec:
                vec = gc(f, cache)
                embedded += 1
            if not vec:
                continue
            out.append({
                "path": str(f),
                "title": fm.get("title", ""),
                "status": fm.get("status", ""),
                "created": fm.get("created", ""),
                "valid_from": fm.get("valid_from", fm.get("created", "")),
                # De update-as MOET hier mee (TASK-146). Laat je hem weg, dan
                # leest elke consument 'event' via de default, slaat de
                # supersede-pas alles over en rapporteert 0 -- een nul die
                # "de guard is stuk" betekent in plaats van "niets te doen".
                "volatility": _memory.coerce_volatility(fm.get("volatility"), body),
                "body": body.strip(),
                "vec": vec,
            })
        if embedded:
            p.note(f"let op: {embedded} van de {len(out)} vectoren kwamen niet uit "
                   f"de index en zijn opnieuw geembed (traag)")
    return out


def neighbour_map(items: list, threshold: float) -> dict:
    """{path -> [(other_path, cos), ...]} for every pair with cos > threshold.

    The ONE neighbour computation per sweep (TASK-191): similar_pairs and
    neighbor_counts previously each ran their own probe — via the index a
    duplicated KNN sweep, and on the brute fallback two full O(n^2)
    triangles of 15m26s each ("samen was het een half uur per sweep").
    Computed once at the LOWEST consumer threshold, it filters exactly:
    every comparison downstream is strict '>', so a 0.75 map filtered at
    0.80 equals the 0.80 map.

    De voortgang telt PAREN, niet rijen: rij i doet n-i vergelijkingen, dus
    een schatting uit "rijen gedaan" zit er ruim twee keer naast (gemeten:
    24 minuten voorspeld waar 11 resteerde, TASK-153).
    """
    # De index draagt precies deze vectoren en is voor deze vraag gebouwd. Op
    # de levende vault scheelt dat 15m26s tegen enkele seconden (TASK-154). Hij
    # geeft None zodra hij de vraag niet betrouwbaar kan beantwoorden, en dan
    # blijft de brute weg hieronder staan -- die is traag maar altijd juist.
    from_index = _neighbours_from_index(items, threshold)
    if from_index is not None:
        return from_index
    n = len(items)
    out: dict = {it["path"]: [] for it in items}
    with Progress(n * (n - 1) // 2, f"paren zoeken boven {threshold}") as p:
        for i in range(n):
            for j in range(i + 1, n):
                s = emb.cosine(items[i]["vec"], items[j]["vec"])
                if s > threshold:
                    out[items[i]["path"]].append((items[j]["path"], s))
                    out[items[j]["path"]].append((items[i]["path"], s))
            p.step(n - i - 1)
    return out


def similar_pairs(items: list, threshold: float, neighbours: dict = None) -> list:
    """Vind alle paren current-items met cosine(a, b) > threshold.

    Returns list[tuple(a, b, sim)] gesorteerd van hoog naar laag sim.
    ``neighbours`` mag een gedeelde neighbour_map zijn, ook een die op een
    LAGERE drempel of een ruimere item-set is berekend: de drempel- en
    lidmaatschapsfilters hieronder maken hem exact equivalent aan een verse
    berekening (strikte '>' overal; membership via by_path).
    """
    nmap = neighbours if neighbours is not None else neighbour_map(items, threshold)
    by_path = {it["path"]: it for it in items}
    seen, pairs = set(), []
    for path, buren in nmap.items():
        if path not in by_path:
            continue
        for other, cos in buren:
            if cos <= threshold or other not in by_path:
                continue
            sleutel = (path, other) if path < other else (other, path)
            if sleutel in seen:
                continue
            seen.add(sleutel)
            pairs.append((by_path[sleutel[0]], by_path[sleutel[1]], cos))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def neighbor_counts(items: list, threshold: float, neighbours: dict = None) -> dict:
    """Tel het aantal verwante buren (cosine > threshold) per item.

    Returns dict[path -> int]. Symmetric: als a en b elkaars buren zijn telt
    het voor beide. Zelfde deel-contract als similar_pairs: een gedeelde map
    op een lagere drempel/ruimere set wordt hier exact gefilterd.
    """
    nmap = neighbours if neighbours is not None else neighbour_map(items, threshold)
    own = {it["path"] for it in items}
    counts = {p: 0 for p in own}
    for path, buren in nmap.items():
        if path not in own:
            continue
        counts[path] = sum(1 for other, cos in buren
                           if cos > threshold and other in own)
    return counts


#: Promptversie: ophogen bij ELKE wijziging aan SUPERSEDE_SYSTEM, zodat een
#: sluiting herleidbaar blijft tot de prompt die haar veroorzaakte. Wordt in de
#: reden in de closed-log gestempeld (TASK-150).
#:
#: v3 (TASK-169): supersede requires full coverage, the same correction as
#: RECONCILE_SYSTEM v3. Of 237 hand-labelled historic closures 27% narrowed
#: (the successor dropped facts) and only 11% genuinely replaced substance;
#: closing on "a different value" alone loses knowledge via the status filter.
SUPERSEDE_PROMPT_VERSION = 3

#: Dezelfde behandeling als RECONCILE_SYSTEM kreeg in TASK-144: de volgorde van
#: de vragen expliciet, en de vraag "gaat dit uberhaupt over hetzelfde?"
#: vooraan.
#:
#: Aanleiding is een meting, geen gevoel. Op de 149 echte supersede-paren van
#: deze vault herkende de oude prompt er 30% in de band 0.70-0.90 (en 0% boven
#: 0.95, waar de teksten bijna identiek zijn en "er verandert niets" een
#: verdedigbaar antwoord is). Zeven van de tien echte vervangingen bleven dus
#: liggen.
#:
#: "Bij twijfel: false" blijft staan en hoort te blijven staan. Wat verandert
#: is wat er VOOR die regel gebeurt: het model kreeg een definitie en geen
#: procedure, en moest zelf bedenken of "vervangt" ook slaat op een waarde die
#: is bijgesteld of een probleem dat is opgelost. Nu staat dat er.
SUPERSEDE_SYSTEM = (
    "Je beoordeelt of een NIEUWERE memory een OUDERE vervangt. Loop deze vragen "
    "in volgorde af en stop bij de eerste die past:\n"
    "1. Gaan ze over HETZELFDE onderwerp? Nee -> supersede: false. Klaar.\n"
    "2. Geeft de nieuwere een ANDERE waarde, status of uitkomst voor dat "
    "onderwerp dan de oudere? Denk aan: een gewijzigde instelling, een "
    "teruggedraaid besluit, een opgelost probleem ('knop mist terugkoppeling' "
    "-> 'knop toont nu een status'), of een veranderde situatie ('Jim zoekt "
    "baan' -> 'Jim heeft baan'). Kies dan supersede: true, maar ALLEEN als de "
    "nieuwere ook alles van blijvende waarde uit de oudere meeneemt. Bevat de "
    "oudere feiten die de nieuwere NIET heeft -- een terugvalpad, een concrete "
    "parameter, een procedure -- dan is sluiten kennisverlies: die feiten "
    "verdwijnen uit recall. Dan supersede: false.\n"
    "3. Vullen ze elkaar aan zonder elkaar tegen te spreken, of zeggen ze "
    "hetzelfde? -> supersede: false.\n"
    "Antwoord UITSLUITEND met JSON: {\"supersede\": true|false, "
    "\"reason\": \"<kort>\"}. Bij twijfel: false."
)


def judge_supersede(new_text: str, old_text: str) -> bool:
    import _llm
    raw = _llm.generate(f"NIEUWER:\n{new_text}\n\nOUDER:\n{old_text}\n\nOordeel (JSON):",
                        system=SUPERSEDE_SYSTEM)
    if not raw:
        return False
    obj = _llmjson.first_object(raw) or {}
    return obj.get("supersede") is True


RECHECK_SYSTEM = (
    "Je beoordeelt of een memory DUIDELIJK RUIS, onjuist of waardeloos is en ingetrokken moet worden. "
    "Antwoord UITSLUITEND met JSON: {\"retract\": true|false, \"reason\": \"<kort>\"}. "
    "Bij twijfel: false. Retract ALLEEN als het aantoonbaar slecht is."
)


def judge_recheck(text: str) -> bool:
    """Vraag het LLM of deze memory duidelijk ruis/onjuist is en ingetrokken moet worden.

    FAIL-SAFE-TO-KEEP: None / parse-fout / ontbrekende sleutel / {"retract": false}
    → False (KEEP). Retract ALLEEN bij expliciete {"retract": true}.
    Spiegelt de shape van judge_supersede.
    """
    import _llm
    raw = _llm.generate(f"Geheugen:\n{text}\n\nOordeel (JSON):", system=RECHECK_SYSTEM)
    if not raw:
        return False
    obj = _llmjson.first_object(raw) or {}
    return obj.get("retract") is True


OPEN_STATUSES = ("current", "unverified")


def exact_duplicate_groups(statuses=OPEN_STATUSES) -> list:
    """Groepeer OPEN memories op genormaliseerde body; alleen groepen > 1.

    Bewust ZONDER embeddings, anders dan current_items(). Twee redenen: gelijke
    body is een exacte vaststelling waarvoor een vector niets toevoegt, en deze
    pass moet ook werken wanneer het embedmodel onbereikbaar is -- juist dan
    stapelen duplicaten zich op.

    Een lege body telt niet mee. Die zouden allemaal op elkaar lijken zonder dat
    er iets gedupliceerd is.
    """
    from collections import defaultdict
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return []
    groepen = defaultdict(list)
    for f in sorted(mdir.glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") not in statuses:
            continue
        sleutel = (body or "").strip()
        if not sleutel:
            continue
        groepen[sleutel].append({
            "path": str(f),
            "created": fm.get("created", ""),
            "valid_from": fm.get("valid_from", fm.get("created", "")),
            "source_session": fm.get("source_session", ""),
        })
    return [g for g in groepen.values() if len(g) > 1]


def exact_duplicate_pass(dry_run: bool = False) -> int:
    """Sluit byte-identieke memories; houd er per groep een over.

    Deterministisch en zonder LLM. supersede_pass hiernaast is voor memories die
    op elkaar LIJKEN -- daar is een oordeel nodig, en daar kan een oordeel ook
    fout zijn. Bij een identieke body valt er niets te oordelen; een judge zou
    daar alleen ruis en kosten toevoegen.

    WELKE BLIJFT: de oudste op event-tijd (valid_from, anders created). Daarna
    telt of de bestandsnaam een collision-volgnummer draagt: een `-2`/`-3` is per
    definitie de LATERE schrijver, dus het ongenummerde bestand is het origineel
    en blijft. Zonder die regel zou een sortering op pad het genummerde bestand
    houden -- '-' sorteert voor '.', dus '...-resources-2.md' komt voor
    '...-resources.md'. Op de echte vault koos hij zo consequent de dubbel in
    plaats van het origineel. Als laatste een tie-break op pad, zodat de uitkomst
    reproduceerbaar is en niet afhangt van de volgorde van het bestandssysteem.

    IDENTIEKE BODY, AFWIJKENDE FRONTMATTER (andere source_session, andere
    created) -- de keuze, expliciet: de dubbelen worden GESLOTEN, niet
    samengevoegd. Hun frontmatter blijft gewoon in het gesloten bestand staan,
    inclusief de eigen source_session, en superseded_by wijst naar de
    behoudene. Er gaat dus geen herkomst verloren en de relatie is expliciet.
    Samenvoegen zou de behouden memory muteren om informatie te bewaren die al
    bewaard is -- meer beweging, geen extra kennis.

    Omkeerbaar: niets wordt verwijderd. Een gesloten memory terugzetten is
    status weer op current en superseded_by weg.
    """
    import _memory
    import re as _re
    _volgnummer = _re.compile(r"-\d+$")

    def _rang(it):
        stem = Path(it["path"]).stem
        return (it.get("valid_from") or "",
                it.get("created") or "",
                1 if _volgnummer.search(stem) else 0,
                it["path"])

    gesloten = 0
    for groep in exact_duplicate_groups():
        geordend = sorted(groep, key=_rang)
        houden, rest = geordend[0], geordend[1:]
        stem = Path(houden["path"]).stem
        for dubbel in rest:
            if dry_run:
                gesloten += 1
                continue
            if _memory.set_status(dubbel["path"], "superseded",
                                  superseded_by=[stem],
                                  reason="exact_duplicate_pass: byte-identieke body"):
                gesloten += 1
    return gesloten


#: Vanaf welke cosinus twee memories aan de judge worden voorgelegd.
#:
#: Was 0.85. Gemeten op 101 echte supersede-paren uit deze vault (P1a): 70%
#: van de paren haalt 0.85, 93% haalt 0.75. De drie LAAGSTE cosinussen zijn
#: juist de inhoudelijke gevallen -- "de Rescan-knop mist visuele terugkoppeling"
#: -> "de Rescan-knop toont nu 'Scanning...'" staat op 0.704, het schoolvoorbeeld
#: van een opgelost probleem, en viel onder beide drempels. Het venster stond
#: dus op de verkeerde band gericht.
#:
#: Kosten: 10 kandidaatparen worden er 163 (gemeten over de hele corpus),
#: ongeveer drie minuten judge-tijd voor de hele vault. Dat is te doen.
#:
#: Wat die 163 vandaag OPLEVEREN is nul, en dat hoort hier te staan zodat een
#: nul in de heartbeat later niet als kapotte guard gelezen wordt: de
#: volatility-guard (TASK-146) slaat elk paar over waarvan een kant een
#: gebeurtenis is, en 1572 van de 1595 memories dragen geen label en gelden dus
#: als gebeurtenis. Gemeten: 163 paren boven 0.75, 0 bereiken de judge. Deze
#: verlaging werkt pas mee naarmate nieuwe captures een label meebrengen.
#:
#: En zelfs met labels is het venster niet het zelfcorrigerende mechanisme: op
#: de paren die de judge WEL ziet herkent hij 30% van de echte supersessies
#: (band 0.70-0.90, qwen3.5:4b). Zoeken was nooit het knelpunt; oordelen wel.
#: Zie docs/research/supersede-window-2026-08-13.md.
#:
#: Deze verlaging mocht pas nadat een onterecht gesloten memory ergens
#: zichtbaar werd. Dat was de blokkade: /kennisbank:review loopt alleen de
#: unverified-wachtrij en recall filtert op current, dus een sluiting
#: verscheen NERGENS. Sinds TASK-150 staat elke sluiting in de closed-log en
#: is ze met `memory-doctor.py reopen` terug te draaien.
SUPERSEDE_THRESHOLD = 0.75


def supersede_pass(threshold: float = SUPERSEDE_THRESHOLD, judge_fn=None,
                   get_cached_fn=None, items=None, neighbours=None) -> int:
    import _memory
    judge_fn = judge_fn or judge_supersede
    # items mag een gedeelde snapshot zijn (TASK-191): drie passes laadden elk
    # het volledige corpus (~1600 file-reads per pass). De snapshot wordt aan
    # het einde gepruned van wat DEZE pass sloot, zodat de volgende pass
    # dezelfde wereld ziet als een verse reload zou tonen.
    if items is None:
        items = current_items(get_cached_fn=get_cached_fn)
    done = 0
    superseded_paths = set()
    for a, b, _sim in similar_pairs(items, threshold, neighbours=neighbours):
        # Bepaal nieuwer/ouder op EVENT-tijd (valid_from, fallback created;
        # tie-break op created). Ordenen op created alleen zou een laat
        # gecaptured OUD feit als 'nieuwer' aanmerken en het echt nieuwere
        # feit sluiten met een geinverteerd geldigheidsinterval.
        def _when(it):
            return (it.get("valid_from") or it.get("created") or "",
                    it.get("created") or "")
        newer, older = (a, b) if _when(a) >= _when(b) else (b, a)
        if older["path"] in superseded_paths or newer["path"] in superseded_paths:
            continue
        # Een gebeurtenis wordt nooit gesloten en sluit nooit (TASK-146). Twee
        # log-regels over verschillende sessies lezen makkelijk als
        # bijna-duplicaten; op 0.85 kon dit paar elkaar opeten. Nu is dat
        # structureel onmogelijk in plaats van een oordeel dat het model elke
        # keer goed moet hebben.
        if "event" in (newer.get("volatility"), older.get("volatility")):
            continue
        if judge_fn(newer["body"], older["body"]):
            # Bi-temporele sluiting: het oude feit gold tot het nieuwe inging.
            until = newer.get("valid_from") or newer.get("created") or ""
            if _memory.set_status(older["path"], "superseded",
                                  superseded_by=[Path(newer["path"]).stem],
                                  valid_until=until or None,
                                  reason=("supersede_pass: cosine boven de drempel "
                                          "en de judge zei dat het nieuwe het oude vervangt")):
                superseded_paths.add(older["path"])
                done += 1
    if superseded_paths:
        items[:] = [it for it in items if it["path"] not in superseded_paths]
    return done


def recheck_pass(judge_fn=None, limit: int = 20, items=None) -> int:
    """Hercontrole van current memories: retract ALLEEN bij expliciete ruis-signaal.

    judge_fn(text: str) -> bool: True = retract, False = keep.
    FAIL-SAFE: standaard judge_recheck retourneert False bij twijfel/model-down.
    Nooit wrongly retracten op een dode judge.
    """
    import _memory
    judge_fn = judge_fn or judge_recheck
    if items is None:
        items = current_items()
    done = 0
    retracted = set()
    for it in items[:limit]:
        if judge_fn(it["body"]):
            if _memory.set_status(it["path"], "retracted"):
                retracted.add(it["path"])
                done += 1
    if retracted:
        items[:] = [it for it in items if it["path"] not in retracted]
    return done


#: Buurdrempel voor cluster-promotie; als constante zodat de sweep de map op
#: min(SUPERSEDE_THRESHOLD, CLUSTER_THRESHOLD) kan berekenen zonder een tweede
#: kopie van het getal.
CLUSTER_THRESHOLD = 0.80


def cluster_promote_pass(threshold: float = CLUSTER_THRESHOLD, min_neighbors: int = 2,
                         get_cached_fn=None, items=None, neighbours=None) -> int:
    import re
    if items is None:
        items = current_items(get_cached_fn=get_cached_fn)
    counts = neighbor_counts(items, threshold, neighbours=neighbours)
    done = 0
    for it in items:
        if counts.get(it["path"], 0) < min_neighbors:
            continue
        p = Path(it["path"])
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "promote_candidate:" in raw:
            continue
        # split_frontmatter, niet raw.split("---", 2): dat tweede ziet een
        # "---" IN een waarde ook als fence. Een memory-titel met streepjes
        # raakte daardoor stil beschadigd terwijl deze pass succes rapporteerde.
        # Zelfde fout als in _memory.set_status; beide call-sites zijn hiermee
        # gesloten.
        fm, body = split_frontmatter(raw)
        if not fm:
            continue
        new_fm = fm.rstrip("\n") + "\npromote_candidate: true"
        try:
            p.write_text("---\n" + new_fm + "\n---\n" + body, encoding="utf-8")
            done += 1
        except OSError:
            continue
    return done
