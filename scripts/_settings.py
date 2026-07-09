#!/usr/bin/env python3
"""_settings.py - KennisBank achtergrond-automatiek toggles.

Eén plat JSON-bestand op $VAULT/kennisbank-settings.json is de bron van waarheid
voor welke achtergrond-automatiek draait. get()/set() zijn de enige lezer en
schrijver, zodat key-namen en formaat nergens driften.

Fail-open op lezen: ontbrekend bestand, ongeldige JSON of een ontbrekende key
geeft de meegegeven default terug, nooit een exceptie. Stdlib only, geen hyphen
in de naam zodat scripts het kunnen importeren na sys.path.insert (idem
_vaultpath.py).

CLI:
    python _settings.py get <key> [default]   -> print 1/0, exit 0
    python _settings.py set <key> <1|0|true|false>
    python _settings.py init                   -> schrijf defaults als afwezig
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Self-locate de vault als KENNISBANK_VAULT ontbreekt (idem aan de hookscripts).
# Dit script woont in <vault>/.claude/scripts/, dus parents[2] == <vault>.
os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

FILENAME = "kennisbank-settings.json"

# Canonieke toggles en hun default als de key (of het bestand) ontbreekt.
# Eén bron voor het command, setup.sh en de upgrade-skill.
DEFAULTS = {
    "auto_archive": False,
    "distill_notify": True,
    "embed_index": True,
    "daily_graphify": True,
    # Geheugen-subsysteem (spec fase 1). Kern-functionaliteit → default aan,
    # bewust afwijkend van de opt-in-conventie van auto_archive.
    "memory_capture": True,
    "memory_recall": True,
    # Retrieval-feedbackloop: passief en lokaal, dus default aan.
    "usage_telemetry": True,
    # Optionele LLM-laatste-redmiddel voor temporele recall (Laag 3): normaliseert
    # exotisch/compositioneel taalgebruik via een lokaal Ollama-model wanneer de
    # deterministische tabellen (Laag 1) en dateparser (Laag 2) falen. Niet-
    # deterministisch pad → bewust default UIT (opt-in). Resultaten worden gecachet.
    "activity_llm_fallback": False,
}

_TRUTHY = ("1", "true", "yes", "y", "on")


def settings_path() -> Path:
    return vault_root() / FILENAME


def _load() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key: str, default: bool) -> bool:
    """Lees een toggle. Ontbrekend bestand/key of parse-fout -> default.

    De docs nodigen uit om het JSON-bestand met de hand te bewerken. Een
    string-waarde (bv. "false") wordt daarom via _TRUTHY genormaliseerd, zodat
    "false"/"0"/"no" niet per ongeluk truthy is (bool("false") == True)."""
    val = _load().get(key, default)
    if isinstance(val, str):
        return val.strip().lower() in _TRUTHY
    return bool(val)


def set(key: str, value: bool) -> None:
    """Schrijf een toggle atomisch (tempfile + os.replace). Behoudt onbekende
    keys zodat een nieuwere store-versie niet kapot gaat op een oudere schrijver."""
    data = _load()
    data[key] = bool(value)
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".kbset-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def init() -> bool:
    """Schrijf het defaults-bestand als het nog niet bestaat. Return True als
    geschreven, False als het al bestond."""
    p = settings_path()
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(DEFAULTS), indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return True


def migrate() -> bool:
    """Voeg ontbrekende DEFAULTS-keys toe aan een bestaand settings-bestand zonder
    bestaande waarden te wijzigen. Bestaat het bestand niet, val terug op init().
    Return True als er iets geschreven is. Idempotent.

    Corrupt bestand (niet-leeg, ongeldige JSON): weiger stil (return False, schrijf niets).
    Zelfde principe als register-hooks: corrupt → weiger, niet overschrijven."""
    p = settings_path()
    if not p.exists():
        return init()
    raw = p.read_text(encoding="utf-8")
    if raw.strip():
        try:
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            import sys as _sys
            print(f"_settings: {p} is geen geldige JSON; migrate() weigert te overschrijven.",
                  file=_sys.stderr)
            return False
        if not isinstance(data, dict):
            data = {}
    else:
        data = {}
    missing = {k: v for k, v in DEFAULTS.items() if k not in data}
    if not missing:
        return False
    data.update(missing)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _cli(argv: list[str]) -> int:
    if not argv:
        print("usage: _settings.py get|set|init|migrate ...", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "get":
        if len(argv) < 2:
            print("usage: _settings.py get <key> [default]", file=sys.stderr)
            return 2
        key = argv[1]
        default = DEFAULTS.get(key, False)
        if len(argv) >= 3:
            default = argv[2].lower() in _TRUTHY
        print("1" if get(key, default) else "0")
        return 0
    if cmd == "set":
        if len(argv) < 3:
            print("usage: _settings.py set <key> <1|0|true|false>", file=sys.stderr)
            return 2
        set(argv[1], argv[2].lower() in _TRUTHY)
        return 0
    if cmd == "init":
        print("written" if init() else "exists")
        return 0
    if cmd == "migrate":
        print("migrated" if migrate() else "current")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
