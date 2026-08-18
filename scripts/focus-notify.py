#!/usr/bin/env python3
"""focus-notify.py - surface the shared current_focus block at SessionStart.

The read side of TASK-201. Runs as a NOTIFICATIONS job under the session-start
coordinator, which since TASK-202 delivers that phase per client -- so every
client gets the same answer to "what is being worked on right now", not only
the first one to start.

Contract identical to memory-notify: SessionStart additionalContext JSON when
there is something to say, nothing at all otherwise. Empty or absent block ->
silence; an empty focus is the designed idle state, not a fault. Fail-open:
always exit 0.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _focus  # noqa: E402


def main() -> int:
    text = _focus.read_focus()
    if text:
        sys.stdout.write(json.dumps({
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "KennisBank current focus: " + text,
            }
        }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
