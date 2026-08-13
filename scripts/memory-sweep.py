#!/usr/bin/env python3
"""memory-sweep.py - autonome capture-sweep (extract -> dedup -> reconcile -> judge -> schrijf).

Verwerkt pending transcripts (sinds de .swept-watermark) tot geheugen-files. Per
transcript: tekst -> chunks -> per chunk kandidaten extraheren -> embedden + dedup
tegen bestaande memory -> reconcile tegen gelijkende bestaande memories
(ADD/SUPERSEDE/NOOP op schrijfmoment, Mem0-patroon via _reconcile) -> onafhankelijk
judgen -> schrijven met status (current bij expliciet hoog-zeker, anders unverified),
evidence_basis=agent, source_session, en bi-temporele valid_from (= sessiedatum uit
de transcriptnaam; capture-tijd blijft created). Een SUPERSEDE sluit het oude memory
met valid_until. Daarna een deterministische expire-pass (stempelt ook valid_until).
Schrijft een heartbeat-status.

Gegate op memory_capture. Alle LLM/embed-aanroepen lopen via mockbare seams.
Fail-soft: model onbereikbaar -> stopt netjes, memory blijft staan, heartbeat meldt.

Stdlib. Usage: python3 memory-sweep.py [--max N] [--all]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _embeddings as emb  # noqa: E402
import _extract  # noqa: E402
import _judge  # noqa: E402
import _llm  # noqa: E402
import _memory  # noqa: E402
import _settings  # noqa: E402
import _sweepstate as ss  # noqa: E402
import _sweeputil as su  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"
EMBED_RETRY_ATTEMPTS = 3
EMBED_RETRY_BACKOFF_SECONDS = 0.25

# Sessiedatum uit de transcriptnaam, bv. "2026-06-25-llmwiki-....jsonl".
SESSION_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _producer_id() -> str:
    """Actor-id van de actieve extract-keten (TASK-90 E5): '<provider>/<model>'.
    Fail-soft -> "" (niet-herleidbare producties dragen geen stempel)."""
    try:
        provs = _llm.providers()
        if provs:
            return f"{provs[0]}/{_llm.model_for(provs[0])}"
    except Exception:
        pass
    return ""


def _session_date(name: str, fallback: str) -> str:
    """Event-tijd van een transcript: leidende ISO-datum uit de bestandsnaam,
    anders de fallback (capture-datum). Voedt valid_from."""
    m = SESSION_DATE_RE.match(name)
    return m.group(1) if m else fallback


def _model_reachable() -> bool:
    """Probe ZOWEL chat als embed upfront. True alleen als beide beschikbaar zijn.

    Symmetrisch: een embed-only-outage is dezelfde klasse als een chat-outage —
    als we toch zouden doorgaan, worden alle kandidaten via embed_failed
    overgeslagen maar het transcript alsnog 'swept' gemarkeerd → permanent
    capture-verlies (de .swept-watermark is append-only).
    """
    return bool(_llm.generate("ping")) and bool(emb.embed("ping"))


def _embed_with_retry(text: str) -> list | None:
    """Embed candidate text with a short retry loop for transient backend None."""
    attempts = max(1, int(EMBED_RETRY_ATTEMPTS))
    for attempt in range(attempts):
        vec = emb.embed(text)
        if vec is not None:
            return vec
        if attempt < attempts - 1 and EMBED_RETRY_BACKOFF_SECONDS > 0:
            time.sleep(EMBED_RETRY_BACKOFF_SECONDS)
    return None


OPEN_STATUSES = ("current", "unverified")


def _dedup_items() -> list:
    """Bouw de dedup-pool: ALLE 09-memory-files (via cache), met status en
    valid_until erbij. Alle statussen doen mee zodat --all-rebuilds idempotent
    blijven, maar de dup-beslissing weegt open/gesloten en het
    geldigheidsvenster mee (zie _dup_skip)."""
    out, cache = [], emb.load_cache()
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return out
    for f in mdir.glob("**/*.md"):
        v = emb.get_cached(f, cache)
        if not v:
            continue
        try:
            fm, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
            body = ""
        out.append({
            "vec": v,
            "status": fm.get("status", ""),
            "valid_until": fm.get("valid_until", ""),
            "body_key": su.body_key(body),
        })
    return out


def _dup_skip(vec, valid_from: str, items: list, threshold: float = 0.92) -> bool:
    """Era-bewuste duplicaat-check.

    >threshold tegen een OPEN memory (current/unverified): her-capture ->
    skip (idempotentie zonder LLM-kosten). >threshold tegen een GESLOTEN
    memory (superseded/retracted/expired): alleen skip als de kandidaat uit
    hetzelfde tijdperk komt (valid_from <= valid_until) of het venster
    onbekend is (legacy zonder valid_until). Een her-assertie met LATERE
    valid_from is een flip-back ("Jim zoekt weer een baan") en moet door
    naar de reconcile-laag in plaats van stil te verdwijnen.
    """
    for it in items:
        v = it.get("vec")
        if not v or emb.cosine(vec, v) <= threshold:
            continue
        if it.get("status") in OPEN_STATUSES:
            return True
        vu = it.get("valid_until", "")
        if not vu or (valid_from or "") <= vu:
            return True
    return False


def _expire_pass() -> int:
    """Deterministisch: current memory met expires < vandaag -> expired.

    Muteert alleen het frontmatter-blok (via _memory.set_status) en stempelt
    de bi-temporele sluiting: valid_until = de expires-datum. Telt alleen mee
    als de inhoud daadwerkelijk veranderd is.
    """
    today = date.today().isoformat()
    n = 0
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return 0
    for f in mdir.glob("**/*.md"):
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if fm.get("status") == "current" and fm.get("expires") and fm["expires"] < today:
            if _memory.set_status(f, "expired", valid_until=fm["expires"]):
                n += 1
    return n


#: Drempel voor "unverified en blijft liggen". Staat hier omdat de SWEEP hem
#: voortaan telt; memory-notify leest de uitkomst en rekent niets meer zelf.
ROT_HOURS = 48


def _rot_count() -> "int | None":
    """Tel de unverified memories die blijven liggen. None als het niet lukt.

    Deze telling stond tot TASK-76 in memory-notify, op de SESSIESTART-weg, waar
    hij elk .md-bestand in 09-memory las: gemeten 509 ms van de 543 ms die die
    hook kostte. Het bezwaar was niet dat getal maar de richting -- de kosten
    groeiden mee met de geheugenlaag, dus elke memory die KennisBank erbij
    leerde maakte de sessiestart trager.

    Hier is de scan gratis: de sweep draait toch al in de losgekoppelde worker en
    leest de geheugenlaag sowieso.
    """
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location(
            "memory_doctor", os.path.join(here, "memory-doctor.py"))
        md = importlib.util.module_from_spec(spec)
        sys.modules["memory_doctor"] = md
        spec.loader.exec_module(md)
        return int(md.rot_count(ROT_HOURS))
    except Exception:
        return None


def _note_pass_failure(s: dict, key: str, exc: BaseException) -> None:
    """Record WHY a maintenance pass produced nothing.

    Elke pass stond in `try: ... except Exception: 0`. Een time-out, een
    ImportError en een rustige run leverden daardoor exact dezelfde regel in de
    heartbeat op: nul. Dat is dezelfde faalvorm als TASK-143 een laag lager --
    daar slikte de seam een model dat nooit antwoordde, hier slikt de
    orkestrator een pass die nooit draaide.

    De teller blijft een int (0), want lezers rekenen daarop. De reden komt
    ernaast te staan, en telt mee in `errors` zodat memory-notify het bij de
    volgende sessiestart meldt via een kanaal dat al bestaat.
    """
    s.setdefault("pass_errors", {})[key] = f"{type(exc).__name__}: {exc}"[:200]
    s["errors"] = s.get("errors", 0) + 1
    print(f"memory-sweep: pass '{key}' faalde: {type(exc).__name__}: {exc}",
          file=sys.stderr)


def _run_pass(s: dict, key: str, fn) -> None:
    """Draai één onderhoudspass en houd vast of hij het gehaald heeft."""
    try:
        s[key] = fn()
    except Exception as e:
        s[key] = 0
        _note_pass_failure(s, key, e)


def _write_heartbeat(summary: dict) -> None:
    """Schrijf de heartbeat-status naar <vault>/.claude/memory-sweep-status.json."""
    hb = vault_root() / ".claude" / HEARTBEAT
    out = dict(summary)
    out["last_run"] = datetime.now(timezone.utc).isoformat()
    out["provider"] = _llm.providers()[0] if _llm.providers() else ""
    out["is_local"] = _llm.is_local()
    # Bewust ALTIJD, ook wanneer het model onbereikbaar was en de sweep vroeg
    # terugkeert: de telling is een lokale scan en heeft met Ollama niets te
    # maken. Hem alleen op het geslaagde pad schrijven zou de melding stil laten
    # verdwijnen juist wanneer er iets aan de hand is.
    rot = _rot_count()
    if rot is not None:
        out["rot"] = rot
        out["rot_hours"] = ROT_HOURS
    try:
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


#: Hoeveel chunks van één transcript de extractor leest, en hoeveel memories dat
#: transcript maximaal mag opleveren. Beide stonden op 6 en 20, gekozen toen een
#: chunk 30-56 s kostte omdat het judge-model eerst nadacht (TASK-143). Na die fix
#: kost een chunk 5-6 s en is de oude rem alleen nog verlies.
#:
#: Gemeten over vier lange transcripts (198, 171, 154 en 33 chunks), 120 chunks
#: door de echte extractor:
#:
#:   uniek uit chunk 1-6 : 101 kandidaten
#:   uniek uit chunk 7+  : 361 kandidaten  = 78% van alle unieke kennis
#:   duplicaten          : 4 van 466 = 0,9%
#:   opbrengst per chunk : 4,2 (1-5) 4,2 (6-10) 4,3 (11-15) 3,7 (16-20) 2,9 (26-30)
#:
#: De aanname onder de oude cap -- later in een sessie is herhaling -- is daarmee
#: weerlegd: er is geen knik, en bijna niets wordt dubbel gezegd.
#:
#: max_memories_per_transcript was in de praktijk de BINDENDE rem, niet max_chunks:
#: bij ~4 kandidaten per chunk was 20 memories al na vijf chunks op.
MAX_CHUNKS = int(os.environ.get("KB_SWEEP_MAX_CHUNKS", "").strip() or 40)
MAX_MEMORIES_PER_TRANSCRIPT = int(
    os.environ.get("KB_SWEEP_MAX_MEMORIES", "").strip() or 60)

#: Bovengrens op één sweep-run, in chunks. De sweep is losgekoppeld maar deelt de
#: GPU met het embedding-model dat de retrieval-hot-path bedient; tien transcripts
#: van 40 chunks zou 40 minuten aaneengesloten modelwerk zijn. Bij 5-6 s per chunk
#: is 150 chunks ongeveer een kwartier. Wat niet past blijft pending en komt de
#: volgende run aan de beurt -- de watermark wordt alleen gezet voor transcripts
#: die HELEMAAL verwerkt zijn.
CHUNK_BUDGET = int(os.environ.get("KB_SWEEP_CHUNK_BUDGET", "").strip() or 150)


def run_sweep(max_transcripts: int = 10, max_chunks: int = MAX_CHUNKS,
              max_memories_per_transcript: int = MAX_MEMORIES_PER_TRANSCRIPT,
              ignore_watermark: bool = False,
              chunk_budget: int = CHUNK_BUDGET) -> dict:
    """Verwerk pending (of alle) transcripts naar memory-files.

    Bij ignore_watermark=True worden ALLE *.jsonl in 01-raw/transcripts/ verwerkt,
    ongeacht de .swept-watermark. Dedup voorkomt dubbele memory-files (idempotent).
    max_memories_per_transcript begrenst het aantal geschreven memories per
    source_session, zodat een mega-transcript niet onbeperkt facetten dumpt.

    Returns een samenvatting-dict met sleutels:
        enabled, processed, written, current, unverified, duplicates, expired, errors
    """
    s = {
        "enabled": True,
        "processed": 0,
        "written": 0,
        "current": 0,
        "unverified": 0,
        "duplicates": 0,
        "expired": 0,
        "errors": 0,
        "embed_failed": 0,
        "model_unreachable": False,
        # Zichtbaar maken hoeveel van het aangeboden materiaal daadwerkelijk is
        # gelezen. Zonder deze twee is "5 memories geschreven" niet te
        # onderscheiden van "5 memories geschreven en 300 chunks genegeerd".
        "chunks_read": 0,
        "chunks_skipped": 0,
        "budget_reached": False,
        # Leeg = elke pass heeft gedraaid. Een nul in een teller hierboven
        # betekent dan echt "niets te doen" en niet "gecrasht" (TASK-148).
        "pass_errors": {},
        "superseded": 0,
        "rechecked_retracted": 0,
        "promote_marked": 0,
        "reconciled_superseded": 0,
        "reconcile_noop": 0,
    }

    # Gate: als memory_capture uit staat, vroeg terugkeren (maar heartbeat wel schrijven).
    if not _settings.get("memory_capture", True):
        s["enabled"] = False
        _write_heartbeat(s)
        return s

    # Bouw todo VOOR de probe-guard: ignore_watermark pakt ALLE transcripts (geen cap),
    # normaal alleen pending met max_transcripts-limiet.
    # Bij --all belooft het commando volledigheid; de cap breekt die belofte.
    if ignore_watermark:
        tdir = vault_root() / "01-raw" / "transcripts"
        todo = sorted(tdir.glob("*.jsonl")) if tdir.exists() else []
    else:
        todo = ss.pending()[:max_transcripts]

    # IMPORTANT 1: upfront model-bereikbaarheidsprobe — alleen als er werk is.
    # Een sweep tijdens een model-outage mag NOOIT transcripts als 'swept' markeren;
    # anders zijn ze permanent verloren (de .swept-watermark is append-only).
    if todo and not _model_reachable():
        s["model_unreachable"] = True
        _write_heartbeat(s)
        return s

    existing = _dedup_items()
    existing_body_keys = {it.get("body_key") for it in existing if it.get("body_key")}
    today = date.today().isoformat()

    # Reconcile-pool: bestaande memories met body/status/valid_from/vec,
    # waartegen nieuwe kandidaten op schrijfmoment worden gereconciled
    # (ADD/SUPERSEDE/NOOP). Bewust current+unverified: een nieuw feit mag ook
    # een nog niet geverifieerd ouder feit sluiten. De dedup-pool hierboven
    # omvat ALLE files (idempotentie van --all-rebuilds), maar laat flip-backs
    # tegen gesloten memories door via het era-venster in _dup_skip.
    # Fail-soft: zonder _reconcile (partial deploy) valt alles terug op ADD —
    # capture mag nooit stoppen op een ontbrekende reconcile-laag.
    try:
        import _maintenance as _mnt_pool
        import _reconcile
        _reconcile_fn = _reconcile.reconcile
        pool = _mnt_pool.current_items(statuses=("current", "unverified"))
    except Exception:
        _reconcile_fn = lambda body, vf, vec, items: {"action": "ADD", "supersedes": []}  # noqa: E731
        pool = []

    for tp in todo:
        # Budget-stop TUSSEN transcripts, nooit erbinnen: een half verwerkt
        # transcript zou gemarkeerd worden als gedaan en de rest voorgoed
        # kwijtraken. Wat hier afvalt blijft pending voor de volgende run.
        if not ignore_watermark and chunk_budget and s["chunks_read"] >= chunk_budget:
            s["budget_reached"] = True
            break
        try:
            transcript = ss.transcript_text(tp)
            valid_from = _session_date(tp.name, today)
            chunks = su.chunk(transcript)
            # Bij --all geen chunk-cap: de rebuild-belofte geldt voor het hele transcript.
            chunk_iter = chunks if ignore_watermark else chunks[:max_chunks]
            s["chunks_read"] += len(chunk_iter)
            s["chunks_skipped"] += max(0, len(chunks) - len(chunk_iter))
            written_for_tp = 0
            for ch in chunk_iter:
                if max_memories_per_transcript and written_for_tp >= max_memories_per_transcript:
                    break
                for cand in _extract.extract_candidates(ch):
                    if max_memories_per_transcript and written_for_tp >= max_memories_per_transcript:
                        break
                    title = cand.get("title", "memory")
                    body = cand.get("body", "")
                    body_key = su.body_key(body)
                    if body_key in existing_body_keys:
                        s["duplicates"] += 1
                        continue
                    vec = _embed_with_retry(body)
                    # BUG 4: als embed None teruggeeft (backend down), sla kandidaat over;
                    # een geheugenbestand zonder vector is niet te dedupliceren.
                    if vec is None:
                        s["embed_failed"] += 1
                        continue
                    if _dup_skip(vec, valid_from, existing):
                        s["duplicates"] += 1
                        continue
                    # Write-time invalidatie (Mem0-patroon): NOOP -> niets
                    # schrijven; SUPERSEDE -> oude memory sluiten na schrijven.
                    rec = _reconcile_fn(body, valid_from, vec, pool)
                    if rec["action"] == "NOOP":
                        s["reconcile_noop"] += 1
                        continue
                    verdict = _judge.judge(body)
                    # Fail-safe: alleen bij expliciet hoog-zeker 'current' promoveren.
                    status = "current" if verdict.get("verdict") == "current" else "unverified"
                    # Collision-guard: bereken uniek pad VOOR het schrijven. Een
                    # bezette slug met IDENTIEKE body is geen collision om
                    # omheen te nummeren maar een her-capture; dan blijft het
                    # bestaande bestand staan en schrijven we niets.
                    path, bestaat_al = _memory.unique_memory_path(
                        title, created=today, body=body)
                    if bestaat_al:
                        s["duplicates"] += 1
                        continue
                    rendered = _memory.render(
                        title, body,
                        status=status,
                        evidence_basis="agent",
                        source_session=tp.name,
                        created=today,
                        valid_from=valid_from,
                        memory_type=_memory.coerce_memory_type(cand.get("type")),
                        importance=_memory.coerce_importance(verdict.get("importance")),
                        model_id=_producer_id(),
                        prompt_version=_extract.EXTRACT_PROMPT_VERSION,
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(rendered, encoding="utf-8")
                    # Superseden ALLEEN als de kandidaat zelf 'current' is
                    # gejudged: quarantaine-kennis (unverified) mag geen
                    # geverifieerd feit sluiten. Wordt de kandidaat later
                    # alsnog current, dan pakt de supersede-pass (vangnet,
                    # current-only) het paar op.
                    if status == "current":
                        for old in rec["supersedes"]:
                            if _memory.set_status(
                                    old["path"], "superseded",
                                    superseded_by=[path.stem],
                                    valid_until=valid_from,
                                    reason="reconcile op schrijfmoment: nieuw feit vervangt dit"):
                                s["reconciled_superseded"] += 1
                                pool = [it for it in pool if it["path"] != old["path"]]
                    existing.append({"vec": vec, "status": status, "valid_until": ""})
                    existing_body_keys.add(body_key)
                    pool.append({
                        "path": str(path), "title": title, "status": status,
                        "created": today, "valid_from": valid_from,
                        "body": body, "vec": vec,
                    })
                    s["written"] += 1
                    s[status] += 1
                    written_for_tp += 1
            ss.mark([tp.stem])
            s["processed"] += 1
        except Exception:
            s["errors"] += 1

    # Fail-soft: een malformed memory-file mag de sweep-afronding (heartbeat,
    # onderhoudspas) niet blokkeren.
    try:
        s["expired"] = _expire_pass()
    except Exception:
        s["errors"] += 1

    # De onderhoudspas gebruikt het LLM; draai 'm NOOIT als het model onbereikbaar
    # is. Onvoorwaardelijke check (de capture-probe is gegate op 'todo' en vuurt niet
    # als er geen pending transcripts zijn) -> anders zinloze LLM-calls op een dode
    # judge. De judge-seams zijn al fail-safe-to-keep, dit is defense-in-depth.
    if not _model_reachable():
        s["model_unreachable"] = True
        _write_heartbeat(s)
        return s

    # Cross-memory onderhoud (v2): supersede, 2e-lijn-hercontrole, cluster-promotie.
    try:
        import _maintenance as _mnt
        # Exacte duplicaten EERST, en zonder LLM. Scheelt supersede_pass een
        # judge-aanroep per duplicaatpaar, en belangrijker: een identieke body
        # hoort niet aan een oordeel onderworpen te worden dat fout kan gaan.
        _run_pass(s, "exact_duplicates_closed", _mnt.exact_duplicate_pass)
        _run_pass(s, "superseded", _mnt.supersede_pass)
        _run_pass(s, "rechecked_retracted", _mnt.recheck_pass)
        _run_pass(s, "promote_marked", _mnt.cluster_promote_pass)
    except Exception as e:
        # De import zelf faalde: geen enkele pass heeft gedraaid.
        _note_pass_failure(s, "maintenance", e)

    _write_heartbeat(s)
    return s


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        # Zonder deze tak viel --help door de hand-geparste argv heen en STARTTE
        # het script een echte sweep op de vault. "Wat doet dit ook alweer?" hoort
        # geen schrijfactie te zijn.
        print("Usage: memory-sweep.py [--max N] [--max-per-transcript N] [--all]\n"
              f"  --max                 transcripts per run (default {10})\n"
              f"  --max-per-transcript  memories per transcript "
              f"(default {MAX_MEMORIES_PER_TRANSCRIPT})\n"
              "  --all                 negeer de watermark en de caps; verwerk alles\n"
              f"\nChunks per transcript: {MAX_CHUNKS} (KB_SWEEP_MAX_CHUNKS)\n"
              f"Budget per run: {CHUNK_BUDGET} chunks (KB_SWEEP_CHUNK_BUDGET)")
        return 0
    mx = 10
    # De module-default, niet 20: anders overschrijft de CLI-tak stilzwijgend de
    # gemeten waarde, en sweep-launch.py start de sweep juist via de CLI.
    mm = MAX_MEMORIES_PER_TRANSCRIPT
    if "--max" in argv:
        try:
            mx = int(argv[argv.index("--max") + 1])
        except Exception:
            mx = 10
    if "--max-per-transcript" in argv:
        try:
            mm = int(argv[argv.index("--max-per-transcript") + 1])
        except Exception:
            mm = MAX_MEMORIES_PER_TRANSCRIPT
    ignore = "--all" in argv
    s = run_sweep(max_transcripts=mx, max_memories_per_transcript=mm,
                  ignore_watermark=ignore)
    if s.get("enabled"):
        print(
            f"memory-sweep: {s['processed']} transcripts, {s['written']} geschreven "
            f"({s['current']} current, {s['unverified']} unverified), "
            f"{s['duplicates']} dup, {s['reconcile_noop']} noop, "
            f"{s['reconciled_superseded']} superseded-at-write, "
            f"{s['expired']} expired, {s['errors']} fouten"
        )
    else:
        print("memory-sweep: uitgeschakeld (memory_capture=false)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"memory-sweep: overgeslagen ({e})", file=sys.stderr)
        sys.exit(0)
