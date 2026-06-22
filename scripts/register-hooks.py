#!/usr/bin/env python3
"""Idempotently register KennisBank hooks in a Claude Code settings.json.

setup.sh calls this once, after deploying the script layer, to wire the two
retrieval hooks into the user's global ``~/.claude/settings.json``:

  * ``SessionStart``     -> build-embed-index.py  (warms the wiki embed cache)
  * ``UserPromptSubmit`` -> kb-retrieve.py        (injects matching wiki snippets)

Without this, a fresh install has a cold cache and the retrieval-dependent
commands (/uitdaag, /brug, /wiki self-rewrite) silently find nothing.

Design constraints:
  * Stdlib only (runs anywhere python3 runs; deployed alongside the other scripts).
  * Non-destructive: existing hooks, permissions, env, and any other settings are
    preserved. Only our two entries are added/updated.
  * Idempotent: re-running deploys the same result — no duplicate entries.
  * Self-healing: if an entry for the same script basename already exists but
    points at a stale path (e.g. the vault moved), its command is updated.
  * Safe: if settings.json exists but is not valid JSON, refuse and exit non-zero
    rather than clobber a hand-edited config.

Usage:
  register-hooks.py <settings.json> <EVENT> <script_path> [<EVENT> <script_path> ...]

Example (as called by setup.sh):
  register-hooks.py ~/.claude/settings.json \\
      SessionStart   <vault>/.claude/scripts/build-embed-index.py \\
      UserPromptSubmit <vault>/.claude/scripts/kb-retrieve.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def build_command(script_path: str) -> str:
    """The hook command string: invoke the script with python3.

    The path is quoted so a vault path containing spaces still runs. Matches the
    project convention (scripts are run via ``python3 path``; the executable bit
    is cosmetic) and works on macOS/Linux and Windows Git Bash alike.
    """
    return f'python3 "{script_path}"'


def load_settings(path) -> dict:
    """Read settings.json into a dict.

    Returns ``{}`` for a missing or blank file. Raises ``ValueError`` if the file
    exists with content that is not valid JSON, so the caller never overwrites a
    config it could not parse.
    """
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{p} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{p} does not contain a JSON object")
    return data


def save_settings(path, settings: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_hook(settings: dict, event: str, script_path: str) -> bool:
    """Ensure ``event`` runs ``script_path`` as a command hook. Idempotent.

    Matches an existing entry by the script's basename: if found, its command is
    updated to the current path (self-heal) and we report change only if it
    actually differed; otherwise a new hook group is appended. Other entries
    under the same event are left untouched.

    Returns True if ``settings`` was modified, False if it was already correct.
    """
    command = build_command(script_path)
    basename = os.path.basename(script_path)

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("settings['hooks'] is not an object")
    event_groups = hooks.setdefault(event, [])
    if not isinstance(event_groups, list):
        raise ValueError(f"settings['hooks']['{event}'] is not a list")

    for group in event_groups:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if not isinstance(h, dict):
                continue
            existing = h.get("command")
            if isinstance(existing, str) and basename in existing:
                if existing == command:
                    return False  # already exactly right -> no-op
                h["command"] = command  # stale path -> self-heal
                return True

    event_groups.append({"hooks": [{"type": "command", "command": command}]})
    return True


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 3 or (len(argv) - 1) % 2 != 0:
        print(
            "usage: register-hooks.py <settings.json> <EVENT> <script_path> "
            "[<EVENT> <script_path> ...]",
            file=sys.stderr,
        )
        return 2

    settings_path = argv[0]
    pairs = [(argv[i], argv[i + 1]) for i in range(1, len(argv), 2)]

    try:
        settings = load_settings(settings_path)
    except ValueError as e:
        print(f"register-hooks: {e}", file=sys.stderr)
        print("register-hooks: laat settings.json ongemoeid; registreer hooks handmatig "
              "(zie CONFIGURATION.md).", file=sys.stderr)
        return 1

    changed = False
    for event, script_path in pairs:
        if ensure_hook(settings, event, script_path):
            changed = True

    if changed:
        save_settings(settings_path, settings)
        print(f"register-hooks: hooks geregistreerd in {settings_path}")
    else:
        print(f"register-hooks: hooks al aanwezig in {settings_path} (geen wijziging)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
