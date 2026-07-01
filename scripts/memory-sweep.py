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

# Sessiedatum uit de transcriptnaam, bv. "2026-06-25-llmwiki-....jsonl".
SESSION_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


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
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
        out.append({
            "vec": v,
            "status": fm.get("status", ""),
            "valid_until": fm.get("valid_until", ""),
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


def _write_heartbeat(summary: dict) -> None:
    """Schrijf de heartbeat-status naar <vault>/.claude/memory-sweep-status.json."""
    hb = vault_root() / ".claude" / HEARTBEAT
    out = dict(summary)
    out["last_run"] = datetime.now(timezone.utc).isoformat()
    out["provider"] = _llm.providers()[0] if _llm.providers() else ""
    out["is_local"] = _llm.is_local()
    try:
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def run_sweep(max_transcripts: int = 10, max_chunks: int = 6,
              ignore_watermark: bool = False) -> dict:
    """Verwerk pending (of alle) transcripts naar memory-files.

    Bij ignore_watermark=True worden ALLE *.jsonl in 01-raw/transcripts/ verwerkt,
    ongeacht de .swept-watermark. Dedup voorkomt dubbele memory-files (idempotent).

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
        try:
            transcript = ss.transcript_text(tp)
            valid_from = _session_date(tp.name, today)
            chunks = su.chunk(transcript)
            # Bij --all geen chunk-cap: de rebuild-belofte geldt voor het hele transcript.
            chunk_iter = chunks if ignore_watermark else chunks[:max_chunks]
            for ch in chunk_iter:
                for cand in _extract.extract_candidates(ch):
                    title = cand.get("title", "memory")
                    body = cand.get("body", "")
                    vec = emb.embed(body)
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
                    # Collision-guard: bereken uniek pad VOOR het schrijven.
                    path = _memory.unique_memory_path(title, created=today)
                    rendered = _memory.render(
                        title, body,
                        status=status,
                        evidence_basis="agent",
                        source_session=tp.name,
                        created=today,
                        valid_from=valid_from,
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
                            if _memory.set_status(old["path"], "superseded",
                                                  superseded_by=[path.stem],
                                                  valid_until=valid_from):
                                s["reconciled_superseded"] += 1
                                pool = [it for it in pool if it["path"] != old["path"]]
                    existing.append({"vec": vec, "status": status, "valid_until": ""})
                    pool.append({
                        "path": str(path), "title": title, "status": status,
                        "created": today, "valid_from": valid_from,
                        "body": body, "vec": vec,
                    })
                    s["written"] += 1
                    s[status] += 1
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
        try:
            s["superseded"] = _mnt.supersede_pass()
        except Exception:
            s["superseded"] = 0
        try:
            s["rechecked_retracted"] = _mnt.recheck_pass()
        except Exception:
            s["rechecked_retracted"] = 0
        try:
            s["promote_marked"] = _mnt.cluster_promote_pass()
        except Exception:
            s["promote_marked"] = 0
    except Exception:
        s["superseded"] = s.get("superseded", 0)
        s["rechecked_retracted"] = s.get("rechecked_retracted", 0)
        s["promote_marked"] = s.get("promote_marked", 0)

    _write_heartbeat(s)
    return s


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    mx = 10
    if "--max" in argv:
        try:
            mx = int(argv[argv.index("--max") + 1])
        except Exception:
            mx = 10
    ignore = "--all" in argv
    s = run_sweep(max_transcripts=mx, ignore_watermark=ignore)
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
