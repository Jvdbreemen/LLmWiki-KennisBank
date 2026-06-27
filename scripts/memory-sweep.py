#!/usr/bin/env python3
"""memory-sweep.py - autonome capture-sweep (extract -> dedup -> judge -> schrijf).

Verwerkt pending transcripts (sinds de .swept-watermark) tot geheugen-files. Per
transcript: tekst -> chunks -> per chunk kandidaten extraheren -> embedden + dedup
tegen bestaande memory -> onafhankelijk judgen -> schrijven met status (current bij
expliciet hoog-zeker, anders unverified), evidence_basis=agent, source_session.
Daarna een deterministische expire-pass. Schrijft een heartbeat-status.

Gegate op memory_capture. Alle LLM/embed-aanroepen lopen via mockbare seams.
Fail-soft: model onbereikbaar -> stopt netjes, memory blijft staan, heartbeat meldt.

Stdlib. Usage: python3 memory-sweep.py [--max N]
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


def _model_reachable() -> bool:
    """Probe het LLM: True als de keten een niet-lege string teruggeeft."""
    return bool(_llm.generate("ping"))


def _existing_memory_vectors() -> list:
    """Bouw de dedup-pool: embed alle bestaande 09-memory-files (via cache)."""
    vecs, cache = [], emb.load_cache()
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return vecs
    for f in mdir.glob("**/*.md"):
        v = emb.get_cached(f, cache)
        if v:
            vecs.append(v)
    return vecs


def _expire_pass() -> int:
    """Deterministisch: current memory met expires < vandaag -> expired.

    Muteert ALLEEN de status-regel binnen het frontmatter-blok (tussen de eerste
    twee --- fences) met een regex-replace, zodat quoted status-waarden én
    een eventueel zelfde patroon in de body niet mis-vervangen worden.
    Telt alleen mee als de inhoud daadwerkelijk veranderd is.
    """
    today = date.today().isoformat()
    n = 0
    mdir = vault_root() / "09-memory"
    if not mdir.exists():
        return 0
    for f in mdir.glob("**/*.md"):
        try:
            txt = f.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(txt)
        except Exception:
            continue
        if fm.get("status") == "current" and fm.get("expires") and fm["expires"] < today:
            # Split op de eerste twee --- fences om frontmatter te isoleren.
            parts = txt.split("---", 2)
            if len(parts) < 3:
                continue
            pre, fm_block, rest = parts
            new_fm_block = re.sub(
                r"^status:.*$", "status: expired", fm_block, count=1, flags=re.MULTILINE
            )
            new_txt = "---".join([pre, new_fm_block, rest])
            if new_txt != txt:
                f.write_text(new_txt, encoding="utf-8")
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


def run_sweep(max_transcripts: int = 10, max_chunks: int = 6) -> dict:
    """Verwerk pending transcripts naar memory-files.

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
    }

    # Gate: als memory_capture uit staat, vroeg terugkeren (maar heartbeat wel schrijven).
    if not _settings.get("memory_capture", True):
        s["enabled"] = False
        _write_heartbeat(s)
        return s

    # IMPORTANT 1: upfront model-bereikbaarheidsprobe — alleen als er pending werk is.
    # Een sweep tijdens een model-outage mag NOOIT transcripts als 'swept' markeren;
    # anders zijn ze permanent verloren (de .swept-watermark is append-only).
    pending_list = ss.pending()[:max_transcripts]
    if pending_list and not _model_reachable():
        s["model_unreachable"] = True
        _write_heartbeat(s)
        return s

    existing = _existing_memory_vectors()
    today = date.today().isoformat()

    for tp in pending_list:
        try:
            transcript = ss.transcript_text(tp)
            for ch in su.chunk(transcript)[:max_chunks]:
                for cand in _extract.extract_candidates(ch):
                    title = cand.get("title", "memory")
                    body = cand.get("body", "")
                    vec = emb.embed(body)
                    # BUG 4: als embed None teruggeeft (backend down), sla kandidaat over;
                    # een geheugenbestand zonder vector is niet te dedupliceren.
                    if vec is None:
                        s["embed_failed"] += 1
                        continue
                    if su.is_duplicate(vec, existing):
                        s["duplicates"] += 1
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
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(rendered, encoding="utf-8")
                    existing.append(vec)
                    s["written"] += 1
                    s[status] += 1
            ss.mark([tp.stem])
            s["processed"] += 1
        except Exception:
            s["errors"] += 1

    s["expired"] = _expire_pass()
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
    s = run_sweep(max_transcripts=mx)
    if s.get("enabled"):
        print(
            f"memory-sweep: {s['processed']} transcripts, {s['written']} geschreven "
            f"({s['current']} current, {s['unverified']} unverified), "
            f"{s['duplicates']} dup, {s['expired']} expired, {s['errors']} fouten"
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
