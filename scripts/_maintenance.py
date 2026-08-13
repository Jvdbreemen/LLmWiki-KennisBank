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

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _llmjson  # noqa: E402
from _frontmatter import parse_frontmatter, split_frontmatter  # noqa: E402
from _progress import Progress  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


def _index_vectors() -> dict:
    """path -> vector for the memory layer, straight out of kb-index.db.

    Fail-soft and best-effort: a missing index, a missing sqlite-vec extension or
    a schema that does not match simply yields {}, and every caller falls back to
    the embedding cache. This is a shortcut, never a dependency.

    Only vectors in the index's own embed_id space are returned, because the
    index stores exactly one space and records it in meta. Mixing spaces would be
    silently wrong: cosine across two models means nothing.
    """
    try:
        import sqlite3
        import sqlite_vec
        db = vault_root() / ".claude" / "kb-index.db"
        if not db.exists():
            return {}
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1.0)
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            row = conn.execute("SELECT value FROM meta WHERE key='embed_id'").fetchone()
            if not row or row[0] != emb.embed_id():
                return {}
            import array
            out = {}
            for path, blob in conn.execute(
                    "SELECT d.path, v.embedding FROM docs d "
                    "JOIN vec_docs v ON v.doc_id = d.doc_id WHERE d.layer='memory'"):
                a = array.array("f")
                a.frombytes(blob)
                out[str(path)] = list(a)
            return out
        finally:
            conn.close()
    except Exception:
        return {}


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
                fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if fm.get("status") not in statuses:
                continue
            vec = from_index.get(str(f))
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


def similar_pairs(items: list, threshold: float) -> list:
    """Vind alle paren current-items met cosine(a, b) > threshold.

    Returns list[tuple(a, b, sim)] gesorteerd van hoog naar laag sim.

    Kwadratisch in het aantal memories: op de levende vault (1595 current
    memories) zijn dat 1,27 miljoen cosinussen en ruim een kwartier rekenen,
    dat tot TASK-153 zwijgend afliep.

    De voortgang telt PAREN, niet rijen. Dat lijkt een detail en is het niet:
    rij i doet n-i vergelijkingen, dus elke volgende rij is korter. Een
    schatting die uit "rijen gedaan" extrapoleert rekent met het gemiddelde
    van de brede rijen aan het begin en zit er ruim twee keer naast (gemeten:
    24 minuten voorspeld waar 11 resteerde). Tellen in de eenheid waarin het
    werk zit, maakt het percentage en de schatting allebei waar.
    """
    pairs = []
    n = len(items)
    with Progress(n * (n - 1) // 2, f"paren zoeken boven {threshold}") as p:
        for i in range(n):
            for j in range(i + 1, n):
                s = emb.cosine(items[i]["vec"], items[j]["vec"])
                if s > threshold:
                    pairs.append((items[i], items[j], s))
            p.step(n - i - 1)
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs


def neighbor_counts(items: list, threshold: float) -> dict:
    """Tel het aantal verwante buren (cosine > threshold) per item.

    Returns dict[path -> int]. Symmetric: als a en b elkaars buren zijn
    telt het voor beide.
    """
    counts = {it["path"]: 0 for it in items}
    n = len(items)
    # Telt paren, om dezelfde reden als similar_pairs: een driehoekslus die
    # rijen telt geeft een schatting die er structureel naast zit.
    with Progress(n * (n - 1) // 2, "buren tellen") as p:
        for i in range(n):
            for j in range(i + 1, n):
                if emb.cosine(items[i]["vec"], items[j]["vec"]) > threshold:
                    counts[items[i]["path"]] += 1
                    counts[items[j]["path"]] += 1
            p.step(n - i - 1)
    return counts


SUPERSEDE_SYSTEM = (
    "Je beoordeelt of een NIEUWERE memory een OUDERE TEGENSPREEKT of vervangt "
    "(bv. 'Jim zoekt baan' -> 'Jim heeft baan'). Antwoord UITSLUITEND met JSON: "
    "{\"supersede\": true|false, \"reason\": \"<kort>\"}. Bij twijfel: false."
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
                   get_cached_fn=None) -> int:
    import _memory
    judge_fn = judge_fn or judge_supersede
    items = current_items(get_cached_fn=get_cached_fn)
    done = 0
    superseded_paths = set()
    for a, b, _sim in similar_pairs(items, threshold):
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
    return done


def recheck_pass(judge_fn=None, limit: int = 20) -> int:
    """Hercontrole van current memories: retract ALLEEN bij expliciete ruis-signaal.

    judge_fn(text: str) -> bool: True = retract, False = keep.
    FAIL-SAFE: standaard judge_recheck retourneert False bij twijfel/model-down.
    Nooit wrongly retracten op een dode judge.
    """
    import _memory
    judge_fn = judge_fn or judge_recheck
    items = current_items()
    done = 0
    for it in items[:limit]:
        if judge_fn(it["body"]):
            if _memory.set_status(it["path"], "retracted"):
                done += 1
    return done


def cluster_promote_pass(threshold: float = 0.80, min_neighbors: int = 2,
                         get_cached_fn=None) -> int:
    import re
    items = current_items(get_cached_fn=get_cached_fn)
    counts = neighbor_counts(items, threshold)
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
