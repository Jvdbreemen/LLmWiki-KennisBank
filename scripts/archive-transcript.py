#!/usr/bin/env python3
"""archive-transcript.py — SessionEnd-hook: archiveer een CC-transcript.

Leest de SessionEnd-hook-JSON op stdin (transcript_path, session_id, cwd, reason)
en kopieert het transcript naar $VAULT/01-raw/transcripts/<datum>-<slug>-<sid8>.jsonl.

FAIL-OPEN, ALTIJD: elke fout logt naar stderr en eindigt met exit 0, zodat de hook
het afsluiten van een sessie nooit blokkeert. Idempotent: dezelfde sessie 2x
archiveren overschrijft alleen als de bron groter is (transcript groeit).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Self-locate de vault als KENNISBANK_VAULT ontbreekt in de hook-env (idem aan
# kb-retrieve.py / build-embed-index.py). Het script woont in
# <vault>/.claude/scripts/, dus parents[2] == <vault>.
os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402
from _common import slugify  # noqa: E402

MIN_BYTES = 200  # lege/-p-transcripts overslaan

# NB: spec-regel 102 noemt een OPTIONELE retry voor de partial-write-race
# (transcript nog niet volledig geschreven). Bewust weggelaten in v1: SessionEnd
# draait synchroon vóór exit (transcript is dan geflusht), en de groei-overschrijf
# in archive() (overschrijft alleen als de bron groter is) is het vangnet als er
# ooit toch een te korte kopie landt en de bron later groeit.


def _date_from_transcript(src: Path) -> str:
    try:
        return datetime.fromtimestamp(src.stat().st_mtime).date().isoformat()
    except OSError:
        return datetime.now().date().isoformat()


def _sid8(session_id: str | None, fallback: str) -> str:
    sid = (session_id or fallback or "").lower()
    cleaned = "".join(c for c in sid if c.isalnum())
    return cleaned[:8] or "noid"


def dest_path(vault: Path, hook: dict, src: Path) -> Path:
    cwd = hook.get("cwd") or ""
    slug = slugify(Path(cwd).name) if cwd else "unknown"
    sid8 = _sid8(hook.get("session_id"), src.stem)
    date = _date_from_transcript(src)
    return vault / "01-raw" / "transcripts" / f"{date}-{slug}-{sid8}.jsonl"


def archive(hook: dict, vault: Path) -> dict:
    tp = (hook.get("transcript_path") or "").strip()
    if not tp:
        return {"status": "error", "reason": "no transcript_path"}
    src = Path(os.path.expanduser(tp))
    if not src.is_file():
        return {"status": "error", "reason": f"source missing: {src}"}
    try:
        size = src.stat().st_size
    except OSError as e:
        return {"status": "error", "reason": str(e)}
    if size < MIN_BYTES:
        return {"status": "skipped-empty", "bytes": size}

    # Session-gekeyde dedup: hergebruik een bestaande archieffile met dezelfde
    # sid8, ongeacht de datum-prefix. Zo levert een SessionEnd-refire (bv. na
    # /clear, of een transcript dat over een dagovergang groeit) GEEN duplicaat.
    tdir = vault / "01-raw" / "transcripts"
    sid8 = _sid8(hook.get("session_id"), src.stem)
    try:
        existing = sorted(tdir.glob(f"*-{sid8}.jsonl"))
    except OSError:
        existing = []
    dst = existing[0] if existing else dest_path(vault, hook, src)
    if dst.exists():
        try:
            if dst.stat().st_size >= size:
                return {"status": "skipped-uptodate", "dest": str(dst)}
        except OSError:
            pass
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError as e:
        return {"status": "error", "reason": str(e)}
    return {"status": "archived", "dest": str(dst), "bytes": size}


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook = json.loads(raw) if raw.strip() else {}
        if not isinstance(hook, dict):
            hook = {}
    except (json.JSONDecodeError, OSError, ValueError):
        hook = {}
    try:
        result = archive(hook, vault_root())
    except Exception as e:  # fail-open
        print(f"[archive-transcript] unexpected: {e}", file=sys.stderr)
        return 0
    if result.get("status") == "error":
        print(f"[archive-transcript] {result.get('reason')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # Wrap ook de entry: een import- of opstartfout mag nooit een niet-nul exit
    # geven (mirror van kb-retrieve.py's fail-open __main__).
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
