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
