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
import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402
import _sweepstate  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"
_STALE_HOURS = 26
#: De cap die de sweep op trap 1 legt (KB_VERIFY_CAP in _groundcheck). Staat hier
#: alleen om de melding te laten uitleggen WAAROM er een achterstand is; de
#: waarheid blijft _groundcheck.
_VERIFY_CAP = int(os.environ.get("KB_VERIFY_CAP", "40"))


def _worker_running(vault: Path) -> bool:
    """Return whether the detached index/sweep worker still owns its lock."""
    try:
        script = Path(__file__).with_name("index-launch.py")
        spec = importlib.util.spec_from_file_location("index_launch", script)
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lock = vault / ".claude" / module.LOCK_NAME
        return lock.exists() and not module.is_stale(lock)
    except Exception:
        return False


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
    rot = _telling(hb.get("rot"))
    if rot is None:
        return None
    uren = hb.get("rot_hours")
    return rot, uren if isinstance(uren, int) else 48


def _telling(v) -> "int | None":
    """Een echte telling uit de heartbeat, of None. Bool is hier geen int."""
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _rot_msgs(hb: dict) -> list:
    """De rot-melding, gesplitst naar wat de lezer eraan kan doen.

    Eén telling gaf één advies, en dat advies was fout zodra de memories al
    beoordeeld waren (TASK-198): de oude regel stuurde naar /kennisbank:settings
    en Ollama terwijl die allebei in orde waren, en noemde de enige weg die wel
    werkt niet. `waiting` is een vraag over de sweep; `undecided` is beoordeeld
    en blijft liggen tot een mens beslist.
    """
    gelezen = _rot(hb)
    if gelezen is None or gelezen[0] <= 0:
        return []
    rot, uren = gelezen
    wacht, onbeslist = _telling(hb.get("rot_waiting")), _telling(hb.get("rot_undecided"))
    if wacht is None or onbeslist is None:
        # Heartbeat van voor TASK-198. De splitsing is onbekend, dus noem geen
        # oorzaak: een verkeerde aanwijzing kost meer dan geen aanwijzing.
        return [f"geheugen: {rot} unverified memories ouder dan {uren}u."]
    msgs = []
    if wacht > 0:
        # NIET naar sweep-launch/Ollama sturen. Dat is dezelfde faalvorm die de
        # `undecided`-tak hieronder al opgelost kreeg: een aanwijzing naar iets
        # dat in orde is. De sweep cap't trap 1 bewust op KB_VERIFY_CAP per run
        # zodat zijn staart begrensd blijft, dus een achterstand na een grote
        # extractie is de VERWACHTE toestand, geen storing. Draait de sweep echt
        # niet, dan meldt de stale-heartbeat-tak dat apart en met eigen tekst.
        msgs.append(f"geheugen: {wacht} unverified memories ouder dan {uren}u "
                    f"wachten op beoordeling; de sweep doet er max "
                    f"{_VERIFY_CAP} per run, dus draai 'kb-verify.py' om de "
                    f"achterstand in een keer af te voeren "
                    f"(--dry-run toont eerst wat er zou promoveren).")
    if onbeslist > 0:
        # NIET /kennisbank:review: dat is de audit-view over de promotie- en
        # sluitingslogboeken en kan alleen `demote` en `reopen`. Een unverified
        # memory staat in geen van beide, dus dat commando verplaatst hem niet.
        # Eén verkeerde aanwijzing vervangen door een andere is geen fix.
        msgs.append(f"geheugen: {onbeslist} beoordeelde memories bleven onbeslisbaar; "
                    f"geen automatisch pad verplaatst die nog - bekijk ze met "
                    f"'memory-doctor.py pending' en beslis per stuk met "
                    f"'memory-doctor.py decide <stem> approve|reject|skip'.")
    return msgs


def notice() -> str:
    msgs = []
    vault = vault_root()
    worker_running = _worker_running(vault)
    hb_path = vault / ".claude" / HEARTBEAT
    hb = {}
    if hb_path.exists():
        try:
            hb = json.loads(hb_path.read_text(encoding="utf-8")) or {}
        except Exception:
            hb = {}
    # The heartbeat describes the last completed run. While the detached
    # worker is active, that old failure is not current evidence and should not
    # surface as a fresh SessionStart warning.
    if hb.get("model_unreachable") and not worker_running:
        msgs.append("geheugen-sweep: LLM/embed was onbereikbaar - capture gepauzeerd "
                    "(transcripts blijven wachten).")
    if isinstance(hb.get("errors"), int) and hb["errors"] > 0:
        msgs.append(f"geheugen-sweep: {hb['errors']} fout(en) in de laatste run.")
    msgs.extend(_rot_msgs(hb))

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
        if stale and not worker_running:
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
