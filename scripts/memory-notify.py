#!/usr/bin/env python3
"""memory-notify.py - SessionStart-health-surface voor het geheugen.

Verzoent 'onzichtbaar' met 'luid bij falen': leest de sweep-heartbeat + de
quarantaine-rot en meldt ALLEEN als er iets mis is (model onbereikbaar, sweep-
fouten, of unverified-rot). Niets mis -> geen output (stil).

SessionStart-output-contract: {"hookSpecificOutput": {"hookEventName":
"SessionStart", "additionalContext": "..."}}. Fail-open: altijd exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402
import _sweepstate  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"
_STALE_HOURS = 26


def _rot(hb: dict) -> "tuple[int, int] | None":
    """Lees de rot-telling AF uit de heartbeat; bereken hem niet.

    Deze functie scande tot TASK-76 zelf de hele geheugenlaag: elk .md-bestand in
    09-memory openen en de frontmatter parsen, bij elke sessiestart. Gemeten 509
    ms van de 543 ms die deze hook kostte -- en erger dan het getal was de
    richting, want de kosten groeiden mee met het aantal memories.

    De uitkomst is bovendien geen live feit: het aantal verandert alleen wanneer
    de sweep/judge draait, en die draait al in de losgekoppelde worker. Daar
    wordt hij nu geteld en in de heartbeat gezet.

    Ontbreekt de sleutel (oude heartbeat, sweep nog nooit gedraaid), dan geeft
    dit None en zwijgt de melding. BEWUST geen terugval op zelf scannen: dat zou
    de kosten terugbrengen op precies het pad waar ze weg moesten. Zelfherstellend,
    want de worker draait bij elke sessiestart.
    """
    rot = hb.get("rot")
    if not isinstance(rot, int) or isinstance(rot, bool):
        return None
    uren = hb.get("rot_hours")
    return rot, uren if isinstance(uren, int) else 48


def notice() -> str:
    msgs = []
    hb_path = vault_root() / ".claude" / HEARTBEAT
    hb = {}
    if hb_path.exists():
        try:
            hb = json.loads(hb_path.read_text(encoding="utf-8")) or {}
        except Exception:
            hb = {}
    if hb.get("model_unreachable"):
        msgs.append("geheugen-sweep: LLM/embed was onbereikbaar - capture gepauzeerd "
                    "(transcripts blijven wachten).")
    if isinstance(hb.get("errors"), int) and hb["errors"] > 0:
        msgs.append(f"geheugen-sweep: {hb['errors']} fout(en) in de laatste run.")
    gelezen = _rot(hb)
    if gelezen is not None and gelezen[0] > 0:
        rot, uren = gelezen
        msgs.append(f"geheugen: {rot} unverified memories ouder dan {uren}u "
                    f"(sweep/judge promoot ze niet - draai /kennisbank:settings of check Ollama).")

    # Signaleer een gestalde/afwezige sweep: pending transcripts + absent/stale heartbeat.
    # Fail-soft: onparseerbare last_run → behandeld als stale (alleen als er pending zijn).
    pending = _sweepstate.pending()
    if pending:
        last_run = hb.get("last_run", "")
        stale = True  # default: aannemen stale als we het niet kunnen bepalen
        if last_run:
            try:
                dt = datetime.fromisoformat(last_run)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                stale = age_hours > _STALE_HOURS
            except Exception:
                stale = True
        if stale:
            n = len(pending)
            ts = last_run or "geen heartbeat"
            msgs.append(
                f"geheugen-sweep lijkt gestald (laatste run {ts} / geen heartbeat) "
                f"terwijl {n} transcript(s) wachten — check sweep-launch/Ollama."
            )

    return " ".join(msgs)


def main() -> int:
    msg = notice()
    if msg:
        sys.stdout.write(json.dumps({
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "KennisBank-geheugen: " + msg,
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
