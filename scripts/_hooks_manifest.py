#!/usr/bin/env python3
"""_hooks_manifest.py - de canonieke lijst van KennisBank-hooks.

Eén bron van waarheid voor register-hooks.py, doctor.sh en de migraties. Een
hook toevoegen is hier één regel; alle consumenten dekken 'm dan automatisch.
Stdlib-only, geen zware imports (doctor.sh importeert dit vanuit een python3 -c).
"""
from __future__ import annotations

# (event, script_basename, matcher_of_None). Alleen KennisBank-hooks; de hooks
# van de gebruiker (bv. caveman) staan hier NIET in en blijven ongemoeid.
HOOKS = [
    ("SessionStart",     "kb-session-start.py",   None),
    ("SessionStart",     "kb-session-end-recover.py", None),
    ("UserPromptSubmit", "kb-retrieve.py",        None),
    ("SessionEnd",       "kb-session-end.py",     None),
    ("PreToolUse",       "kb-presearch.py",       "WebSearch|WebFetch"),
]

# Timeout-plafond per hookscript, in seconden. EEN bron voor alle drie de
# installatiewegen (register-hooks.py voor Claude, install-agent-envs.py voor
# Codex, _copilot.py voor Copilot). Die declareerden elk hun eigen getal, en
# voor Claude werd er helemaal niets geschreven -- geen enkel bestand legde vast
# wat daar de default was, waardoor het budget niet te beredeneren viel.
#
# De sessiestart-waarde is ruim: sinds TASK-63 draait het indexonderhoud
# losgekoppeld, dus het blokkerende deel is de launcher plus capture, import en
# notificaties. Het plafond blijft bewust boven die worst case liggen -- lager
# declareren dan wat er feitelijk kan draaien maakt de situatie slechter, niet
# beter.
TIMEOUTS = {
    "kb-session-start.py": 240,
    "kb-session-end.py": 90,
    "kb-retrieve.py": 30,
    "kb-presearch.py": 30,
    "kb-session-end-recover.py": 30,
    "kb-copilot-capture.py": 30,
}

DEFAULT_TIMEOUT = 30


def timeout(script: str) -> int:
    """Plafond voor een hookscript; DEFAULT_TIMEOUT voor onbekende scripts."""
    return int(TIMEOUTS.get(script, DEFAULT_TIMEOUT))


SILENT_HOOK_SCRIPTS = frozenset()

LEGACY_SESSION_END_SCRIPTS = frozenset({
    "archive-transcript.py",
    "kb-usage-scan.py",
})

# Removed from SessionStart during upgrade, then replaced by the coordinator.
LEGACY_SESSION_START_SCRIPTS = frozenset({
    "build-embed-index.py",
    "build-kb-index.py",
    "build-activity-index.py",
    "sweep-launch.py",
    "memory-notify.py",
    "distill-notify.py",
})


def hooks():
    """Een kopie van het manifest (consumenten mogen muteren zonder de bron te raken)."""
    return list(HOOKS)
