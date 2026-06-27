#!/usr/bin/env python3
"""distill-notify.py — SessionStart-hook + destillatie-watermark.

Zonder argumenten (SessionStart-hook): telt gearchiveerde transcripts in
01-raw/transcripts/ die nog niet gedestilleerd zijn (niet in .distilled) en
injecteert een korte melding als additionalContext. Geen LLM, geen embed.

Met --list-pending: print de pending stems (één per regel) zodat /destilleer een
momentopname van de te verwerken set kan vastleggen.

Met --mark <stem...> (aangeroepen door /destilleer na een geslaagde import+wiki):
APPENDt exact die stems aan .distilled. Markeert nooit meer dan de meegegeven set,
zodat een transcript dat tijdens /wiki binnenkomt niet onterecht 'gedestilleerd' raakt.

FAIL-OPEN, ALTIJD: elke fout eindigt met exit 0 en injecteert niets.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK_NAME = ".distilled"


def _transcripts_dir(vault: Path) -> Path:
    return vault / "01-raw" / "transcripts"


def _read_watermark(vault: Path) -> set[str]:
    wm = _transcripts_dir(vault) / WATERMARK_NAME
    try:
        return {ln.strip() for ln in wm.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def _all_stems(vault: Path) -> list[str]:
    try:
        return sorted(p.stem for p in _transcripts_dir(vault).glob("*.jsonl"))
    except OSError:
        return []


def pending(vault: Path) -> list[str]:
    done = _read_watermark(vault)
    return [s for s in _all_stems(vault) if s not in done]


def mark(vault: Path, stems: list[str]) -> int:
    """Append exact de meegegeven stems aan .distilled (dedup). Markeert nooit
    de hele map: alleen de set die /destilleer daadwerkelijk verwerkte."""
    done = _read_watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    wm = _transcripts_dir(vault) / WATERMARK_NAME
    try:
        wm.parent.mkdir(parents=True, exist_ok=True)
        with wm.open("a", encoding="utf-8") as f:
            for s in new:
                f.write(s + "\n")
    except OSError as e:
        print(f"[distill-notify] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


def _emit_notify(count: int) -> None:
    if count <= 0:
        return
    ctx = (f"{count} gearchiveerde CC-transcript(s) wachten op destillatie. "
           f"Draai /destilleer om ze te importeren en in de wiki te verwerken.")
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))


def main() -> int:
    # stdin leegtrekken (hook geeft JSON; we gebruiken het niet maar lezen het wel)
    try:
        sys.stdin.read()
    except OSError:
        pass
    try:
        vault = vault_root()
        argv = sys.argv[1:]
        if argv and argv[0] == "--mark":
            n = mark(vault, argv[1:])
            print(f"[distill-notify] gemarkeerd: {n} stem(s)", file=sys.stderr)
            return 0
        if argv and argv[0] == "--list-pending":
            for s in pending(vault):
                print(s)
            return 0
        # Alleen het SessionStart-meldpad gate-t op distill_notify. De
        # --mark/--list-pending subcommando's hierboven draaien altijd, zodat
        # /destilleer blijft werken als de melding uit staat. Fail-open: kan de
        # toggle niet gelezen worden, val terug op de default (True = aan).
        try:
            import _settings
            notify = _settings.get("distill_notify", True)
        except Exception:
            notify = True
        if notify:
            _emit_notify(len(pending(vault)))
    except Exception as e:  # fail-open
        print(f"[distill-notify] unexpected: {e}", file=sys.stderr)
        return 0
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
