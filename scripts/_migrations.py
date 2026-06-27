#!/usr/bin/env python3
"""_migrations.py - version-gated migratie-runner voor de KennisBank-vault.

Brengt een vault deterministisch naar VERSION via geordende, idempotente
migraties (dirs, hooks, toggles) en stempelt <vault>/.claude/.kennisbank-version.
Het framework is vooruitkijkend: de huidige migraties zijn idempotent-altijd-
toepasbaar, de version-gating betaalt zich uit bij toekomstige eenrichtings-
migraties. Stdlib-only.

CLI:
    _migrations.py run <vault_root> <settings_json> [--skip-hooks]
    _migrations.py version <vault_root>   -> print de gestempelde versie
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

VERSION = "0.9.0"
STAMP_REL = ".claude/.kennisbank-version"


def _vtuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def read_stamp(vault_root) -> str:
    try:
        return (Path(vault_root) / STAMP_REL).read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def write_stamp(vault_root, version: str) -> None:
    p = Path(vault_root) / STAMP_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(version + "\n", encoding="utf-8")


def _load_sibling(name, filename):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _m_memory_dirs(vault_root, ctx):
    for d in ("09-memory", "09-memory/archive", "01-raw/transcripts"):
        (Path(vault_root) / d).mkdir(parents=True, exist_ok=True)


def _m_register_hooks(vault_root, ctx):
    if ctx.get("skip_hooks"):
        return
    rh = _load_sibling("register_hooks", "register-hooks.py")
    settings_path = ctx["settings_path"]
    # F4: een corrupte globale settings.json blokkeert de rest van de migratie NIET.
    # Corrupt = afzonderlijk probleem; dirs + toggles + stamp gaan gewoon door.
    # doctor.sh zal daarna waarschuwen over ontbrekende hooks.
    try:
        settings = rh.load_settings(settings_path)
    except ValueError as e:
        print(f"  waarschuwing: {e}; hook-registratie overgeslagen (doctor.sh meldt dit later).",
              file=sys.stderr)
        return
    if rh.register_manifest(settings, str(vault_root)):
        rh.save_settings(settings_path, settings)


def _m_memory_toggles(vault_root, ctx):
    # _settings leest de vault uit KENNISBANK_VAULT; zet 'm voor de migratie.
    os.environ["KENNISBANK_VAULT"] = str(vault_root)
    s = _load_sibling("_settings", "_settings.py")
    s.migrate()


# (versie, naam, apply_fn(vault_root, ctx)). Geordend; idempotent.
MIGRATIONS = [
    ("0.9.0", "geheugen-dirs", _m_memory_dirs),
    ("0.9.0", "geheugen-hooks", _m_register_hooks),
    ("0.9.0", "geheugen-toggles", _m_memory_toggles),
]


def pending(vault_root):
    cur = _vtuple(read_stamp(vault_root))
    return [m for m in MIGRATIONS if _vtuple(m[0]) > cur]


def run(vault_root, settings_path, skip_hooks=False):
    """Pas pending migraties toe en stempel VERSION. Een falende migratie
    propageert vóór de stamp zodat een re-run hervat. Return de namen.

    F6: write_stamp alleen als VERSION nieuwer is dan de huidige stamp —
    nooit downgraden (bv. een oudere setup.sh op een nieuwer gestempelde vault)."""
    ctx = {"settings_path": settings_path, "skip_hooks": skip_hooks}
    applied = []
    for version, name, fn in pending(vault_root):
        fn(vault_root, ctx)
        applied.append(name)
    if _vtuple(VERSION) > _vtuple(read_stamp(vault_root)):
        write_stamp(vault_root, VERSION)
    return applied


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "version" and len(argv) >= 2:
        print(read_stamp(argv[1]))
        return 0
    if len(argv) >= 3 and argv[0] == "run":
        skip = "--skip-hooks" in argv[3:]
        applied = run(argv[1], argv[2], skip_hooks=skip)
        print("migrations toegepast: " + (", ".join(applied) if applied else "(geen)"))
        return 0
    print("usage: _migrations.py run <vault_root> <settings_json> [--skip-hooks]\n"
          "   or: _migrations.py version <vault_root>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
