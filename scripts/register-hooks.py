#!/usr/bin/env python3
"""Idempotently register KennisBank hooks in a Claude Code settings.json.

setup.sh calls this once, after deploying the script layer, to wire the
retrieval hooks into the user's global ``~/.claude/settings.json``.

Without this, a fresh install has a cold cache and the retrieval-dependent
commands (/uitdaag, /brug, /wiki self-rewrite) silently find nothing.

Design constraints:
  * Stdlib only (runs anywhere python3/py -3 runs; deployed alongside scripts).
  * Non-destructive: existing hooks, permissions, env, and any other settings are
    preserved. Only our entries are added/updated.
  * Idempotent: re-running deploys the same result — no duplicate entries.
  * Self-healing: if an entry for the same script basename already exists but
    points at a stale path (e.g. the vault moved), its command is updated while
    the existing interpreter prefix (py -3 or python3) is PRESERVED.
  * Safe: if settings.json exists but is not valid JSON, refuse and exit non-zero
    rather than clobber a hand-edited config.
  * Cross-platform: uses 'py -3' on Windows (os.name == 'nt'), 'python3' elsewhere.

Usage:
  register-hooks.py <settings.json> --manifest <vault_root>
  register-hooks.py <settings.json> <EVENT> <script_path> [<EVENT> <script_path> ...]

Example (as called by setup.sh):
  register-hooks.py ~/.claude/settings.json --manifest /path/to/vault
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def interpreter() -> str:
    """De interpreter voor hook-commando's: 'py -3' op Windows, anders 'python3'.

    Windows' py-launcher is de robuuste manier om Python te vinden in de
    hook-uitvoercontext; op POSIX is python3 de conventie."""
    return "py -3" if os.name == "nt" else "python3"


def build_command(
    script_path: str,
    interp: str | None = None,
    *,
    quiet: bool = False,
    event: str = "SessionStart",
) -> str:
    """Build a quoted hook command, optionally through the quiet runner."""
    command = interp or interpreter()
    coordinator = {
        "kb-session-start.py": "claude",
        "kb-session-end.py": "claude",
    }.get(Path(script_path).name)
    if coordinator:
        return f'{command} "{script_path}" --client {coordinator}'
    if quiet:
        wrapper = str(Path(script_path).with_name("quiet-hook.py"))
        return (
            f'{command} "{wrapper}" --client claude --event {event} '
            f'"{script_path}"'
        )
    return f'{command} "{script_path}"'


def _existing_prefix(command: str) -> str | None:
    """De interpreter-prefix (alles t/m de spatie vóór de eerste quote) van een
    bestaand commando, of None als er geen quote in staat."""
    i = command.find('"')
    return command[:i] if i > 0 else None


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


def ensure_hook(
    settings: dict,
    event: str,
    script_path: str,
    matcher=None,
    *,
    quiet: bool = False,
) -> bool:
    """Zorg dat `event` `script_path` als command-hook draait. Idempotent.

    Match op basename: bestaat een entry, dan wordt alleen het PAD ververst en
    de bestaande interpreter-prefix BEHOUDEN (geen py -3 -> python3). Matcher
    wordt alleen bij een nieuwe (append) entry gezet. Andere entries blijven."""
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
                # Self-heal: update path (preserve interpreter prefix) AND matcher.
                # Safe because each KennisBank hook lives in its own group (one hook per group).
                changed = False
                prefix = _existing_prefix(existing)
                desired = build_command(
                    script_path,
                    interp=prefix.strip() if prefix else None,
                    quiet=quiet,
                    event=event,
                )
                if desired != existing:
                    h["command"] = desired  # self-heal pad, behoud interpreter
                    changed = True
                if "statusMessage" in h:
                    h.pop("statusMessage", None)
                    changed = True
                if matcher and group.get("matcher") != matcher:
                    group["matcher"] = matcher  # self-heal ontbrekende/stale matcher
                    changed = True
                return changed

    group: dict
    if matcher:
        group = {"matcher": matcher,
                 "hooks": [{"type": "command", "command": build_command(
                     script_path, quiet=quiet, event=event)}]}
    else:
        group = {"hooks": [{"type": "command", "command": build_command(
            script_path, quiet=quiet, event=event)}]}
    event_groups.append(group)
    return True


def register_manifest(settings: dict, vault_root: str) -> bool:
    """Registreer de volledige _hooks_manifest tegen <vault>/.claude/scripts/."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "_hooks_manifest", os.path.join(here, "_hooks_manifest.py"))
    man = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(man)
    changed = False
    env = settings.setdefault("env", {})
    if not isinstance(env, dict):
        raise ValueError("settings['env'] is not an object")
    if env.get("KENNISBANK_VAULT") != vault_root:
        env["KENNISBANK_VAULT"] = vault_root
        changed = True
    session_groups = settings.setdefault("hooks", {}).get("SessionStart", [])
    if isinstance(session_groups, list):
        kept = []
        coordinator_seen = False
        for group in session_groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept.append(group)
                continue
            entries = []
            for entry in group["hooks"]:
                command = str(entry.get("command", "")) if isinstance(entry, dict) else ""
                if any(script in command for script in man.LEGACY_SESSION_START_SCRIPTS):
                    continue
                if "kb-session-start.py" in command:
                    if coordinator_seen:
                        continue
                    coordinator_seen = True
                entries.append(entry)
            if len(entries) != len(group["hooks"]):
                changed = True
            if entries:
                updated = dict(group)
                updated["hooks"] = entries
                kept.append(updated)
        settings["hooks"]["SessionStart"] = kept
    end_groups = settings.setdefault("hooks", {}).get("SessionEnd", [])
    if isinstance(end_groups, list):
        kept = []
        coordinator_seen = False
        for group in end_groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept.append(group)
                continue
            entries = []
            for entry in group["hooks"]:
                command = str(entry.get("command", "")) if isinstance(entry, dict) else ""
                if any(script in command for script in man.LEGACY_SESSION_END_SCRIPTS):
                    changed = True
                    continue
                if "kb-session-end.py" in command:
                    if coordinator_seen:
                        changed = True
                        continue
                    coordinator_seen = True
                entries.append(entry)
            if entries:
                updated = dict(group)
                updated["hooks"] = entries
                kept.append(updated)
        settings["hooks"]["SessionEnd"] = kept
    for event, script, matcher in man.hooks():
        path = f"{vault_root}/.claude/scripts/{script}"
        if ensure_hook(
            settings,
            event,
            path,
            matcher=matcher,
            quiet=script in man.SILENT_HOOK_SCRIPTS,
        ):
            changed = True
    return changed


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 3 and argv[1] == "--manifest":
        settings_path, vault_root = argv[0], argv[2]
        try:
            settings = load_settings(settings_path)
        except ValueError as e:
            print(f"register-hooks: {e}", file=sys.stderr)
            print("register-hooks: laat settings.json ongemoeid; registreer handmatig "
                  "(zie CONFIGURATION.md).", file=sys.stderr)
            return 1
        changed = register_manifest(settings, vault_root)
        if changed:
            save_settings(settings_path, settings)
            print(f"register-hooks: manifest geregistreerd in {settings_path}")
        else:
            print(f"register-hooks: manifest al aanwezig in {settings_path} (geen wijziging)")
        return 0

    if len(argv) < 3 or (len(argv) - 1) % 2 != 0:
        print("usage: register-hooks.py <settings.json> --manifest <vault_root>\n"
              "   or: register-hooks.py <settings.json> <EVENT> <script_path> "
              "[<EVENT> <script_path> ...]", file=sys.stderr)
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
