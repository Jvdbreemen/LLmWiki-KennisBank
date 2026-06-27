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
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

HEARTBEAT = "memory-sweep-status.json"


def _rot() -> int:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "memory_doctor", os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-doctor.py"))
        md = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(md)
        return md.rot_count(48)
    except Exception:
        return 0


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
    rot = _rot()
    if rot > 0:
        msgs.append(f"geheugen: {rot} unverified memories ouder dan 48u "
                    f"(sweep/judge promoot ze niet - draai /kennisbank:settings of check Ollama).")
    return " ".join(msgs)


def main() -> int:
    msg = notice()
    if msg:
        sys.stdout.write(json.dumps({
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
