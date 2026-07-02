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
    ("SessionStart",     "build-embed-index.py",  None),
    ("SessionStart",     "build-kb-index.py",     None),
    ("SessionStart",     "sweep-launch.py",       None),
    ("SessionStart",     "memory-notify.py",      None),
    ("SessionStart",     "distill-notify.py",     None),
    ("UserPromptSubmit", "kb-retrieve.py",        None),
    ("SessionEnd",       "archive-transcript.py", None),
    ("SessionEnd",       "kb-usage-scan.py",      None),
    ("PreToolUse",       "kb-presearch.py",       "WebSearch|WebFetch"),
]


def hooks():
    """Een kopie van het manifest (consumenten mogen muteren zonder de bron te raken)."""
    return list(HOOKS)
