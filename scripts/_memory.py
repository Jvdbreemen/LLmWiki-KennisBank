#!/usr/bin/env python3
"""_memory.py - format van de ruwe geheugenlaag (09-memory/).

Pure stdlib-bibliotheek: rendert en pareert memory-markdown met frontmatter,
en bouwt paden. Geen netwerk, geen embeddings, geen side-effects bij import.
Underscore-naam zodat scripts het importeren na sys.path.insert (idem _settings).

Frontmatter-contract (spec fase 1, bi-temporeel uitgebreid):
    title: vrije tekst (verplicht)
    type: memory
    memory_type: feit | voorkeur | procedure | beslissing
    volatility: state | event. De UPDATE-as, los van memory_type (de
        ONDERWERP-as). state = een waarde die verandert en dus vervangen
        wordt; event = iets dat gebeurd is en dus blijft staan. Afwezig of
        onherkenbaar -> event, tenzij de body config-vormig is (zie
        coerce_volatility).
    importance: 1-5 (judge-oordeel bij capture; 3 = neutraal)
    status: unverified | current | superseded | retracted | expired
    evidence_basis: getypt | cc-sessie | audio | import | autoresearch | agent
    source_session, created, updated, expires?, superseded_by?, tags
    valid_from: vanaf wanneer het feit geldt (event-tijd; default = created).
        Bewust apart van created (capture-tijd): een laat geïmporteerd
        transcript levert een feit dat al eerder gold.
    valid_until?: tot wanneer het feit gold. Gezet bij superseden en
        expiren; een memory zonder valid_until is open-einde geldig.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import slugify, _today_iso  # noqa: E402
from _frontmatter import parse_frontmatter, split_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

STATUSES = ("unverified", "current", "superseded", "retracted", "expired")
EVIDENCE_BASES = ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent")
# Kennistypes verouderen verschillend: een beslissing heeft lange geldigheid
# met expliciete supersession, een voorkeur is zachter, een procedure is
# stabiel tot de tooling wijzigt, een feit tot de wereld wijzigt. Het type
# maakt verval en retrieval per soort differentieerbaar (CrewAI/Cognee-les).
MEMORY_TYPES = ("feit", "voorkeur", "procedure", "beslissing")
DEFAULT_STATUS = "unverified"
DEFAULT_EVIDENCE = "cc-sessie"
DEFAULT_MEMORY_TYPE = "feit"


def coerce_memory_type(value) -> str:
    """Sanitize een (LLM-geleverd) memory-type; onbekend -> 'feit'."""
    v = str(value or "").strip().lower()
    return v if v in MEMORY_TYPES else DEFAULT_MEMORY_TYPE


# ---------------------------------------------------------------------------
# volatility: de UPDATE-as (TASK-146)
#
# memory_type zegt WAAROVER een memory gaat; geen van zijn vier waarden zegt
# "vervang mij als de waarde verandert". Die regel werd daarom bij elke
# reconcile- en supersede-beslissing opnieuw uit proza afgeleid. Gemeten
# kwaliteit van dat afleiden tegen de eigen supersede-besluiten van de vault:
# 7/20 (qwen3.5:4b), 5/20 (qwen3.5:9b), 4/20 (claude haiku). Een model dat
# drie op de vier keer misgokt hoort die vraag niet te krijgen; de structuur
# hoort het antwoord te dragen.
#
#   state -> mag vervangen en vervangen worden
#   event -> wordt NOOIT superseded en supersedet NOOIT
#
# event is de veilige default omdat geschiedenis vernietigen de onomkeerbare
# fout is, en omdat een afwezig veld dan veilig degradeert: de 1661 bestaande
# memories hebben geen migratie nodig.
# ---------------------------------------------------------------------------
VOLATILITIES = ("state", "event")
DEFAULT_VOLATILITY = "event"

#: Een sleutel die naar een instelling ruikt: bevat een underscore of punt
#: (num_ctx, retrieve_top_n, policy.network_allowed) of is ALL_CAPS
#: (RECONCILE_THRESHOLD). Gewone woorden vallen hier bewust buiten, anders
#: wordt "Robert is een ontwikkelaar" een setting.
#:
#: De ALL-CAPS-tak staat expliciet op hoofdlettergevoelig via (?-i:...). Zonder
#: dat werd hij onder re.IGNORECASE "elk woord van drie letters of meer", en
#: dan las `grid-column: 1 / -1` -- een CSS-regel in proza -- als een
#: instelling. Gemeten op de levende vault: dat was de enige reden dat een
#: layout-memory als state werd geclassificeerd.
_CFG_KEY = (r"[A-Za-z][A-Za-z0-9]*(?:[_.][A-Za-z0-9]+)+"
            r"|(?-i:[A-Z][A-Z0-9_]{2,})")
#: Een waarde die naar een instelling ruikt: getal, decimaal, bool, versie,
#: model-tag (qwen3.5:4b), pad, of een aangehaalde token.
#:
#: De \b achter de bool-woorden is niet cosmetisch. Zonder die grens zit
#: 'aan' in "aangepast", 'uit' in "uitgebreid", 'on' in "ontworpen" en 'off'
#: in "officieel" -- alle vier doodgewone Nederlandse woorden. Gemeten op de
#: levende vault leverde dat vijf valse instellingen op, waaronder "FreeRTOS
#: is officieel afgerond" als 'RTOS is off'.
_CFG_VAL = (r"(?:-?\d+(?:\.\d+)?"
            r"|(?i:true|false|waar|onwaar|aan|uit|on|off|null|none)\b"
            r"|v?\d+(?:\.\d+){1,}|[A-Za-z][\w.-]*:[\w.-]+"
            r"|[~/.]?[\w.-]*[/\\][\w./\\-]+|\"[^\"]{1,40}\"|'[^']{1,40}')")
#: Scheidingstekens tussen sleutel en waarde. De copula ("is", eventueel met
#: 'gelijk aan'/'gezet op') hoort erbij: op de levende vault stond de
#: netwerk-policy als "de standaardwaarde voor 'policy.network_allowed' is
#: 'false'" -- onmiskenbaar een instelling, en zonder deze vorm gemist.
_CFG_SEP = (r"(?:=|:=|:|->|→"
            r"|\s+(?i:is|zijn)(?:\s+(?i:gelijk aan|gezet op|gepind op|ingesteld op))?)")
#: Patroon 1 -- toekenning: `num_ctx = 8192`, `TOP_K: 3`, `policy.x is 'false'`.
#: De optionele quote/backtick achter de sleutel is niet cosmetisch: in proza
#: staat een sleutel bijna altijd aangehaald ("de waarde voor
#: 'policy.network_allowed' is 'false'"), en zonder die tolerantie kwam de
#: scheiding nooit aan de beurt.
_CFG_ASSIGN = re.compile(rf"(?:{_CFG_KEY})[\"'`]?\s*{_CFG_SEP}\s*{_CFG_VAL}")
#: Patroon 2 -- toekenning in proza zonder setting-vormige sleutel, maar dan
#: wel met een toekennend werkwoord EN een config-vormige waarde. "de judge
#: draait op qwen3.5:4b" telt; "Robert draait op koffie" niet, want koffie is
#: geen instelling.
_CFG_PHRASE = re.compile(
    r"\b(?:staat op|draait op|is gepind op|is ingesteld op|is gezet op|"
    r"defaultwaarde is|default is|standaard op|"
    r"is set to|runs on|pinned to|defaults to)\s+" + _CFG_VAL,
    re.IGNORECASE)


def looks_like_config(text: str) -> bool:
    """True als de tekst een huidige INSTELLING beweert (model, drempel,
    versie, pad, vlag).

    Deterministisch en zonder model-aanroep, want de vorm is herkenbaar. Deze
    predicaat is met opzet smal: hij draait alleen op de fallback-weg (het
    extract-label ontbreekt) en wordt gedeeld met kb-state-audit, zodat er
    niet twee definities van "config-vormig" ontstaan die uit elkaar lopen.

    Een versienummer of pad ALLEEN is niet genoeg -- "bug X opgelost in
    v0.29.0" is een gebeurtenis die toevallig een versie noemt. Er moet een
    toekenning zijn: een setting-achtige sleutel of een toekennend werkwoord.
    """
    t = " ".join(str(text or "").split())
    if not t:
        return False
    return bool(_CFG_ASSIGN.search(t) or _CFG_PHRASE.search(t))


def coerce_volatility(value, body: str = "") -> str:
    """Bepaal de update-as van een memory. Volgorde is de hele truc:

      1. extract zegt 'state'  -> state
      2. extract zegt 'event'  -> event, NOOIT overruled
      3. afwezig/onleesbaar    -> config-vormige body? state, anders event

    De deterministische check is dus een VANGNET voor de gevallen waarin het
    model twijfelde, geen tweede mening over een label dat het wel gaf. Dat
    houdt het valse-positief-oppervlak klein: alleen kandidaten zonder label
    met een config-vormige body kunnen verkeerd op state landen, en dat is
    omkeerbaar (de sluiting staat in de closed-log, TASK-150).

    Ook gebruikt bij LEZEN van bestaande memories: de 1661 files zonder veld
    krijgen zo dezelfde regel, zodat de supersede-pas blijft werken op precies
    de memories waar vervangen hoort (instellingen) zonder ooit een
    gebeurtenis te sluiten.
    """
    v = str(value or "").strip().lower()
    if v in VOLATILITIES:
        return v
    return "state" if looks_like_config(body) else DEFAULT_VOLATILITY


def coerce_importance(value) -> int:
    """Sanitize importance naar 1..5; onparseerbaar -> neutraal 3."""
    try:
        imp = int(value)
    except (TypeError, ValueError):
        return 3
    return min(5, max(1, imp))


# Herkomst-klassen voor de injectie-tag (TASK-20). Puur presentatie: mapt
# (evidence_basis, status) op een korte, deterministische herkomst-tag zodat
# het consumerende model mens-herkomst autoritatief leest en autonoom/onbevestigd
# als hint. Geen nieuw frontmatter-veld, geen LLM. 'getypt' = mens typte letterlijk
# (autoritatief, geen kwalificatie); cc-sessie/import/autoresearch/audio = mens-in-lus
# (autoritatief); agent = autonoom geextraheerd (hint).
_HUMAN_IN_LOOP_BASES = ("cc-sessie", "import", "autoresearch", "audio")


def provenance_tag(evidence_basis, status="") -> str:
    """Korte deterministische herkomst/status-tag voor een geinjecteerde memory.

    Twee ORTHOGONALE assen, bewust gescheiden (TASK-20):
      - herkomst-as (wie/hoe vastgelegd): getypt = geen marker (autoritatief);
        cc-sessie/import/autoresearch/audio = "mens-in-lus"; agent = "autonoom" (hint).
      - status-as (is het geverifieerd): status=unverified voegt ", onbevestigd" toe,
        ongeacht de herkomst. "onbevestigd" trackt dus UITSLUITEND de status, niet de
        herkomst -- een agent-memory met status=current is judge-geverifieerd en heet
        daarom NIET onbevestigd, wel "autonoom".

    Vormen:
        getypt (current)     -> "(bron: getypt)"
        cc-sessie (current)  -> "(bron: cc-sessie, mens-in-lus)"
        agent (current)      -> "(bron: agent, autonoom)"
        agent (unverified)   -> "(bron: agent, autonoom, onbevestigd)"
        getypt (unverified)  -> "(bron: getypt, onbevestigd)"

    Fail-soft: onbekende/ontbrekende evidence_basis -> "" (geen tag, nooit crash).
    """
    basis = str(evidence_basis or "").strip().lower()
    stat = str(status or "").strip().lower()
    if basis not in EVIDENCE_BASES:
        return ""
    quals = []
    if basis == "getypt":
        pass  # mens typte letterlijk -> autoritatief, geen herkomst-marker
    elif basis == "agent":
        quals.append("autonoom")  # autonoom geextraheerd -> hint (origin-as, niet status)
    elif basis in _HUMAN_IN_LOOP_BASES:
        quals.append("mens-in-lus")  # mens-in-lus -> autoritatief
    if stat == "unverified":
        quals.append("onbevestigd")  # status-as: los van de herkomst
    inner = "bron: " + basis
    if quals:
        inner += ", " + ", ".join(quals)
    return f"({inner})"


def memory_dir() -> Path:
    return vault_root() / "09-memory"


def memory_path(title: str, created: str | None = None) -> Path:
    date = created or _today_iso()
    return memory_dir() / f"{date}-{slugify(title)}.md"


def _genormaliseerde_body(path: Path) -> "str | None":
    """De body van een memory, zonder frontmatter, whitespace-genormaliseerd."""
    try:
        _fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return (body or "").strip()


def unique_memory_path(title: str, created: str | None = None,
                       body: str | None = None) -> "tuple[Path, bool]":
    """Pad voor een nieuwe memory. Geeft (pad, bestaat_al) terug.

    Een bezette slug is een SIGNAAL, geen hindernis om omheen te nummeren. Deze
    functie voegde blind -2, -3 toe zodra het pad bezet was, en produceerde zo
    byte-identieke memories naast elkaar. Nu wordt eerst de body vergeleken:

      identieke body   -> (bestaand pad, True). De aanroeper schrijft NIET.
      andere body      -> (pad met -2/-3/..., False), zoals voorheen.
      body onbekend    -> nummeren, zoals voorheen; zonder body valt er niets
                          te vergelijken en is stil overslaan gevaarlijker dan
                          een duplicaat.

    BEWUST BEPERKT, en dat hoort erbij: dit vangt alleen duplicaten met DEZELFDE
    slug. Twee memories met verschillende titels maar dezelfde inhoud -- of
    dezelfde inhoud op een andere datum, want de datum zit in de slug -- glippen
    hier per definitie doorheen. Uit de meting op de echte vault dekt deze check
    hooguit 15 van de 42 duplicaatgroepen; de andere 27 kregen een ander
    datumprefix en botsen dus nooit. Die vragen het sweep-mechanisme.
    """
    base = memory_path(title, created)
    if not base.exists():
        return base, False
    nieuw = (body or "").strip()
    stem, suffix, parent = base.stem, base.suffix, base.parent
    n = 2
    kandidaat = base
    while kandidaat.exists():
        if body is not None and _genormaliseerde_body(kandidaat) == nieuw:
            return kandidaat, True
        kandidaat = parent / f"{stem}-{n}{suffix}"
        n += 1
    return kandidaat, False


def _yaml_scalar(s) -> str:
    """Veilige double-quoted scalar voor de minimale frontmatter-parser.
    Sanitize i.p.v. escape (de parser kent geen escapes): embedded quotes ->
    enkele quote, newlines -> spatie, en "---" -> em-dash.

    Die laatste hoort erbij: de sanitizer moet dekken wat een parser aanneemt.
    Een titel met "---" liet set_status het bestand op de verkeerde plek
    splitsen, met stille corruptie tot gevolg. Titels komen uit LLM-extractie
    over transcripts, dus dat is geen theoretisch geval."""
    s = str(s).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()
    s = re.sub(r"-{3,}", "—", s)
    return f'"{s}"'


def _yaml_list(items) -> str:
    if isinstance(items, str):
        items = [items]
    safe = [str(i).replace("\n", " ").strip() for i in (items or [])]
    return "[" + ", ".join(safe) + "]"


def render(title: str, body: str, *, status: str = DEFAULT_STATUS,
           evidence_basis: str = DEFAULT_EVIDENCE, source_session: str = "",
           created: str | None = None, updated: str | None = None,
           valid_from: str | None = None, valid_until: str | None = None,
           expires: str | None = None, superseded_by=None, tags=None,
           memory_type: str = DEFAULT_MEMORY_TYPE, importance: int = 3,
           volatility: str = "", model_id: str = "", prompt_version=None,
           source_chunk: str = "") -> str:
    if status not in STATUSES:
        raise ValueError(f"ongeldige status: {status!r} (verwacht een van {STATUSES})")
    if evidence_basis not in EVIDENCE_BASES:
        raise ValueError(f"ongeldige evidence_basis: {evidence_basis!r}")
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"ongeldig memory_type: {memory_type!r} (verwacht een van {MEMORY_TYPES})")
    importance = coerce_importance(importance)
    # GEEN ValueError zoals hierboven: een verhaspeld LLM-label mag de write
    # niet laten crashen en de capture verliezen. Coercen, zoals memory_type
    # en importance dat al doen.
    volatility = coerce_volatility(volatility, body)
    created = created or _today_iso()
    updated = updated or created
    valid_from = valid_from or created
    lines = ["---",
             f"title: {_yaml_scalar(title)}",
             "type: memory",
             f"memory_type: {memory_type}",
             f"volatility: {volatility}",
             f"importance: {importance}",
             f"status: {status}",
             f"evidence_basis: {evidence_basis}",
             f"source_session: {_yaml_scalar(source_session)}",
             f"created: {created}",
             f"updated: {updated}",
             f"valid_from: {valid_from}"]
    # WHERE in the source this claim came from, as "N/M": chunk N of M. The
    # sweep knows this at capture time and used to discard it, which meant that
    # checking a memory against its own transcript required RETRIEVING the
    # passage again -- and that retrieval finds the right chunk only about half
    # the time (TASK-163). M is the total chunk count of the whole transcript,
    # never the capped slice the run happened to read: a verifier re-chunks the
    # transcript and can only trust N if M matches what it sees.
    if source_chunk:
        lines.append(f"source_chunk: {_yaml_scalar(source_chunk)}")
    if valid_until:
        lines.append(f"valid_until: {valid_until}")
    if expires:
        lines.append(f"expires: {expires}")
    if superseded_by:
        lines.append(f"superseded_by: {_yaml_list(superseded_by)}")
    # Producent-provenance (TASK-90 E5): welk model en welke promptversie deze
    # claim produceerde. Bi-temporeel dekt wanneer; dit dekt waardoor — zonder
    # deze as zijn claims van een slechte promptversie niet selecteerbaar.
    # Beide optioneel: mens-getypte memories hebben geen producent.
    if model_id:
        lines.append(f"model_id: {_yaml_scalar(model_id)}")
    if prompt_version is not None:
        lines.append(f"prompt_version: {int(prompt_version)}")
    lines.append(f"tags: {_yaml_list(tags or [])}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def chunk_from_stamp(source_chunk: str, chunks: list):
    """The chunk this memory was captured from, or None if the stamp is stale.

    The stamp is self-validating on purpose. It records "N/M" and the reader
    re-chunks the transcript itself: if the chunker's settings changed since
    capture, M no longer matches and every N is off by an unknown amount. Then
    the stamp is worth nothing and saying so is the only safe answer -- a
    confidently wrong passage would make the verifier judge a claim against
    text it never came from.
    """
    try:
        n_str, m_str = str(source_chunk or "").split("/")
        n, m = int(n_str), int(m_str)
    except Exception:
        return None
    if m != len(chunks) or not 1 <= n <= len(chunks):
        return None
    return chunks[n - 1]


def write_capture(title: str, body: str, **kw) -> "tuple[Path, bool]":
    """Schrijf een nieuwe memory. Geeft (pad, bestond_al) terug.

    Route ALTIJD via unique_memory_path. Deze functie berekende eerder zelf
    memory_path(title) en schreef onvoorwaardelijk, waardoor een tweede capture
    met een botsende slug een door een mens goedgekeurde memory overschreef:
    status terug naar unverified, de goedgekeurde tekst weg, geen backup, geen
    regel in de review-log, en de aanroeper kreeg 'gelukt' terug. Dat is de
    vernietigingskant van de mens-is-autoriteit-grens, en er is geen prompt
    injection voor nodig: twee keer capturen op hetzelfde onderwerp in een
    sessie is het gewone geval.

    bestond_al=True betekent: byte-identieke inhoud stond er al, er is NIETS
    geschreven, en het bestaande pad komt terug. Een afwijkende body op een
    bezette slug krijgt -2/-3/..., zoals unique_memory_path al deed.
    """
    created = kw.get("created")
    p, bestond_al = unique_memory_path(title, created, body)
    p.parent.mkdir(parents=True, exist_ok=True)
    if bestond_al:
        return p, True
    p.write_text(render(title, body, **kw), encoding="utf-8")
    return p, False


def write(title: str, body: str, **kw) -> Path:
    """Zie write_capture. Blijft alleen het pad teruggeven voor bestaande aanroepers."""
    p, _ = write_capture(title, body, **kw)
    return p


def read_status(path) -> str:
    try:
        fm, _ = parse_frontmatter(Path(path).read_text(encoding="utf-8"))
        status = fm.get("status")
        return status if status in STATUSES else DEFAULT_STATUS
    except Exception:
        return DEFAULT_STATUS


def set_status(path, status: str, superseded_by=None, valid_until: str | None = None,
               reason: str = "") -> bool:
    """Herschrijf de status-regel binnen het frontmatter-blok; optioneel een
    superseded_by-link en/of valid_until (bi-temporele sluiting) zetten.
    Return True als het bestand gewijzigd is.
    Mutatie alleen binnen het frontmatter (tussen de eerste twee --- fences).
    Fail-soft: return False bij ongeldige status of OSError."""
    import re
    if status not in STATUSES:
        return False
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return False
    # split_frontmatter i.p.v. raw.split("---", 2): die laatste ziet ELKE "---"
    # als fence, ook een die in een waarde staat. _yaml_scalar sanitizet quotes
    # en newlines maar niet "---", en titels komen uit LLM-extractie over
    # transcripts -- dus dat gebeurt in de praktijk. Gevolg was: de status werd
    # niet gewijzigd, het bestand raakte beschadigd, en de functie gaf True
    # terug omdat er WEL iets veranderd was. _FENCE_RE is verankerd op ^---$,
    # precies om dit uit te sluiten.
    fm, body = split_frontmatter(raw)
    if not fm:
        return False
    # Replacement altijd via een lambda: een string-replacement interpreteert
    # backslashes als regex-escapes (re.PatternError op bv. een pad of "\x").
    new_fm = re.sub(r"^status:.*$", lambda _m: f"status: {status}",
                    fm, count=1, flags=re.MULTILINE)
    if superseded_by:
        # Elke wikilink in dubbele quotes. Zonder die quotes wordt het
        # [[[slug]]], en dat lezen de twee partijen VERSCHILLEND: de eigen
        # frontmatter-parser maakt er terecht ['[[slug]]'] van, maar strikte YAML
        # -- PyYAML, en daarmee Obsidian -- ziet een drievoudig geneste lijst
        # [[['slug']]]. Functioneel ging er binnen KennisBank dus niets mis, maar
        # in Obsidian staat de eigenschap er verminkt bij. Met quotes komen beide
        # lezers op ['[[slug]]'] uit; test_superseded_by_leest_hetzelfde_in_beide
        # bewaakt dat.
        link = "[" + ", ".join(f'"[[{s}]]"' for s in superseded_by) + "]"
        if re.search(r"^superseded_by:.*$", new_fm, flags=re.MULTILINE):
            new_fm = re.sub(r"^superseded_by:.*$", lambda _m: f"superseded_by: {link}",
                            new_fm, count=1, flags=re.MULTILINE)
        else:
            new_fm = new_fm.rstrip("\n") + f"\nsuperseded_by: {link}\n"
    if valid_until:
        if re.search(r"^valid_until:.*$", new_fm, flags=re.MULTILINE):
            new_fm = re.sub(r"^valid_until:.*$", lambda _m: f"valid_until: {valid_until}",
                            new_fm, count=1, flags=re.MULTILINE)
        else:
            new_fm = new_fm.rstrip("\n") + f"\nvalid_until: {valid_until}\n"
    if new_fm == fm:
        # Geen status-regel gevonden en niets toegevoegd: dan is er niets
        # gebeurd, en dat hoort False te zijn. Succes melden op een no-op was
        # de kern van de bug: memory-sweep telde een supersession die nooit
        # plaatsvond en haalde het item uit de reconcile-pool.
        return False
    new_raw = "---\n" + new_fm.strip("\n") + "\n---\n" + body
    if new_raw == raw:
        return False
    try:
        p.write_text(new_raw, encoding="utf-8")
    except OSError:
        return False
    if status in CLOSED_STATUSES:
        _log_closure(p, status, superseded_by, valid_until, reason)
    return True


#: Statussen waarmee een memory uit de recall-set verdwijnt. Recall filtert op
#: `current`, dus dit is de grens waarachter kennis onzichtbaar wordt.
CLOSED_STATUSES = ("superseded", "retracted", "expired")

CLOSED_LOG = "memory-closed-log.jsonl"


def _log_closure(path: Path, status: str, superseded_by, valid_until, reason: str) -> None:
    """Leg vast dat een memory is gesloten. Append-only, fail-soft.

    Het ontwerp leunt erop dat superseden omkeerbaar is: het bestand blijft
    staan, met `superseded_by` en `valid_until` erbij. Dat is waar op schijf en
    onwaar in de praktijk -- recall filtert op `current`, en de reviewwachtrij
    loopt alleen `unverified`. Een verkeerd gesloten memory verscheen dus
    NERGENS meer, en dat is functioneel hetzelfde als verwijderen (TASK-150).

    Dit logboek is de ingang: wat is er gesloten, waardoor, en waarom. Zonder
    zo'n spoor is "het is terug te draaien" een belofte die niemand kan innen.
    """
    try:
        import json
        from datetime import datetime, timezone
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stem": path.stem,
            "status": status,
            "superseded_by": list(superseded_by) if superseded_by else [],
            "valid_until": valid_until or "",
            "reason": (reason or "")[:300],
        }
        log = vault_root() / ".claude" / CLOSED_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # een logboek mag de sluiting zelf nooit blokkeren


def reopen(path, status: str = "current") -> bool:
    """Draai een sluiting terug: status naar current, sluitingsvelden eruit.

    De tegenhanger van set_status voor de gesloten kant. Zonder deze functie is
    terugdraaien handwerk in een frontmatter-blok, en dan is "omkeerbaar" iets
    wat je alleen op papier bent.
    """
    import re
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return False
    fm, body = split_frontmatter(raw)
    if not fm:
        return False
    new_fm = re.sub(r"^status:.*$", lambda _m: f"status: {status}",
                    fm, count=1, flags=re.MULTILINE)
    new_fm = re.sub(r"^superseded_by:.*$\n?", "", new_fm, flags=re.MULTILINE)
    new_fm = re.sub(r"^valid_until:.*$\n?", "", new_fm, flags=re.MULTILINE)
    if new_fm == fm:
        return False
    try:
        p.write_text("---\n" + new_fm.strip("\n") + "\n---\n" + body, encoding="utf-8")
    except OSError:
        return False
    _log_closure(p, f"reopened->{status}", None, None, "handmatig heropend")
    return True


def recent_closures(limit: int = 20) -> list:
    """De laatste sluitingen, nieuwste eerst. Leeg als er geen logboek is."""
    try:
        import json
        log = vault_root() / ".claude" / CLOSED_LOG
        if not log.exists():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:][::-1]
    except Exception:
        return []


DISCARD_LOG = "memory-noop-log.jsonl"
#: Hoeveel regels het discard-logboek hoogstens houdt. Een --all-rebuild over
#: honderden transcripts kan duizenden NOOPs opleveren; de closed-log heeft dat
#: probleem niet, want sluitingen zijn zeldzaam. Ouder dan dit wordt gesnoeid.
DISCARD_LOG_MAX_LINES = 2000


def log_discard(title: str, body: str, covered_by: str = "",
                reason: str = "", prompt_version=None) -> None:
    """Record a candidate memory that reconcile threw away (NOOP).

    Of the three reconcile actions, NOOP is the only one where the candidate is
    never written. The heartbeat counts how OFTEN that happened; until this log
    nothing said WHAT was discarded, so "is the seam throwing away good
    knowledge?" could only be answered by re-running a measurement.

    It matters because NOOP is the action models get wrong. Measured on 20
    unrelated pairs, the old prompt answered NOOP 25% of the time with reasons
    that amounted to "these are unrelated" -- the definition of ADD (TASK-144).
    The prompt fix took that to 0%, but nothing stops a future prompt, model or
    threshold from bringing it back, and nothing would say so.

    Same rules as the closure log: append-only, fail-soft, never a gate. If the
    log cannot be written the sweep carries on, because capture must not depend
    on bookkeeping.
    """
    try:
        import json
        from datetime import datetime, timezone
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "title": str(title or "")[:200],
            "body": str(body or "")[:1000],
            "covered_by": str(covered_by or ""),
            "reason": str(reason or "")[:300],
            "prompt_version": prompt_version,
        }
        log = vault_root() / ".claude" / DISCARD_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _trim_discard_log(log)
    except Exception:
        pass  # a record must never block the sweep


def _trim_discard_log(log: Path) -> None:
    """Keep the discard log bounded, oldest first.

    Trimming only when the file is meaningfully over the limit, so a long
    rebuild does not rewrite the whole file on every single line.
    """
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) <= DISCARD_LOG_MAX_LINES * 1.25:
            return
        keep = lines[-DISCARD_LOG_MAX_LINES:]
        log.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception:
        pass


def recent_discards(limit: int = 20) -> list:
    """The most recently discarded candidates, newest first."""
    try:
        import json
        log = vault_root() / ".claude" / DISCARD_LOG
        if not log.exists():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:][::-1]
    except Exception:
        return []
# --- Menselijke review van unverified memories (TASK-89) ---------------------
#
# Eén gesloten actieset, gedeeld door de Atlas-sidecar (POST /memory/decide),
# de CLI (memory-doctor.py pending/decide), het /kennisbank:review-command en
# de MCP-tools. "Systeem stelt voor, mens beslist" had buiten Atlas geen
# ingang; TASK-23 (31 gestuwde unverified memories, opgeruimd met een one-off
# script) is het bewijs dat die ingang nodig is.
#
# skip is een EXPLICIETE no-op (Mem0-patroon): zonder no-op-optie forceer je
# de beslisser tot actie en krijg je ruis in plaats van uitgestelde oordelen.

DECISIONS = {"approve": "current", "reject": "retracted", "skip": None}
REVIEW_LOG_RELPATH = Path(".claude") / "memory-review-log.jsonl"


class ReviewError(Exception):
    """Reviewfout met HTTP-achtige code (400 invalid, 404 missing, 409 state,
    500 write-failure) zodat Atlas hem 1-op-1 op DocError kan mappen en de
    CLI hem als foutregel kan tonen."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = int(code)


def review_log_path() -> Path:
    return vault_root() / REVIEW_LOG_RELPATH


def pending_reviews(limit=None) -> list:
    """Unverified memories, oudste eerst (created, dan stem). Puur lezen.

    Velden per item: stem, title, created, age_days, memory_type, importance,
    evidence_basis, snippet — genoeg voor een beslisregel in command of GUI
    zonder het bestand nogmaals te openen.
    """
    from datetime import date, datetime
    mdir = memory_dir()
    if not mdir.exists():
        return []
    out = []
    for f in sorted(mdir.glob("**/*.md")):
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if str(fm.get("status", "")).strip() != "unverified":
            continue
        created = str(fm.get("created", "")).strip()
        try:
            age_days = (date.today() - datetime.fromisoformat(created).date()).days
        except Exception:
            age_days = None
        snippet = " ".join(body.split())[:240]
        out.append({
            "stem": f.stem,
            "title": str(fm.get("title", "")).strip().strip("'\""),
            "created": created,
            "age_days": age_days,
            "memory_type": coerce_memory_type(fm.get("memory_type")),
            "importance": coerce_importance(fm.get("importance")),
            "evidence_basis": str(fm.get("evidence_basis", "")).strip(),
            "snippet": snippet,
        })
    out.sort(key=lambda x: (x["created"] or "9999", x["stem"]))
    return out[:limit] if limit else out


def _append_review_log(entry: dict) -> None:
    """Audit-append, fail-soft: telemetrie mag een genomen besluit nooit
    terugdraaien of blokkeren. De statuswijziging is dan al duurzaam."""
    import json
    try:
        p = review_log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def decide(stem: str, decision: str, via: str = "cli") -> dict:
    """Voer één reviewbeslissing uit. Crash-veilige volgorde (llm_wiki #614):

    1. valideer alles (beslissing, stem, bestand, status);
    2. schrijf de statuswijziging DUURZAAM (set_status);
    3. pas daarna de audit-regel en het succes-antwoord.

    Elke fout vóór of tijdens stap 2 -> ReviewError, en het item blijft
    unverified in de queue. Een review-flow die bij falen doet alsof de mens
    besliste, ondermijnt de hele "mens beslist"-belofte.

    skip schrijft niets aan het bestand (expliciete no-op) maar wordt wél
    gelogd: uitgesteld oordeel is informatie voor de doctor-teller.
    """
    if decision not in DECISIONS:
        opts = "|".join(DECISIONS)
        raise ReviewError(400, f"onbekende beslissing: {decision!r} ({opts})")
    if not stem or "/" in stem or "\\" in stem or ".." in stem:
        raise ReviewError(400, "ongeldige stem")
    mem_root = memory_dir().resolve()
    target = (mem_root / f"{stem}.md").resolve()
    if mem_root not in target.parents:
        raise ReviewError(400, "pad buiten 09-memory")
    if not target.is_file():
        raise ReviewError(404, "memory-fragment niet gevonden")
    current = read_status(target)
    if current != "unverified":
        raise ReviewError(409, f"status is {current}, alleen unverified is beslisbaar")

    new_status = DECISIONS[decision]
    if new_status is None:
        result = {"status": "skipped", "stem": stem, "new_status": "unverified"}
    else:
        if not set_status(target, new_status):
            raise ReviewError(500, "statuswijziging niet doorgevoerd (set_status faalde)")
        result = {"status": "ok", "stem": stem, "new_status": new_status}

    from datetime import datetime, timezone
    _append_review_log({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stem": stem, "decision": decision,
        "new_status": result["new_status"], "via": via,
    })
    return result


def review_counts(days: int = 30) -> dict:
    """{approve, reject, skip} uit het audit-log binnen ``days``; fail-soft."""
    import json
    from datetime import datetime, timedelta, timezone
    counts = {"approve": 0, "reject": 0, "skip": 0}
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with review_log_path().open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                    ts = datetime.fromisoformat(str(e.get("ts", "")))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= cutoff and e.get("decision") in counts:
                        counts[e["decision"]] += 1
                except Exception:
                    continue
    except OSError:
        pass
    return counts
