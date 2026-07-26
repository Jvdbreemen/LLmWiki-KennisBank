#!/usr/bin/env python3
"""Achtergrondjob: ververs de remote-refs voor de drift-check.

Waarom een eigen script en niet een vlag op git-upstream-check.py: index-launch
start zijn jobs als `[python, pad]` zonder argumenten. Een `--fetch`-modus zou
dus eerst de runner moeten verbouwen. Een los script van tien regels is de
helderdere weg.

De logica zelf staat NIET hier. refresh_remote() woont in git-upstream-check.py,
naast de code die de uitkomst gebruikt -- anders zouden twee plekken los van
elkaar moeten weten welke remote erbij hoort.

Fail-open en stil, zoals elke job in de worker: een mislukte fetch betekent
hooguit dat de drift-telling een sessie ouder is.
"""
from __future__ import annotations

import importlib.util
import os
import sys


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "git_upstream_check", os.path.join(here, "git-upstream-check.py"))
    mod = importlib.util.module_from_spec(spec)
    # Registreren vóór exec_module: modules die dataclasses of typing gebruiken
    # zoeken zichzelf op via sys.modules en breken anders.
    sys.modules["git_upstream_check"] = mod
    spec.loader.exec_module(mod)
    mod.refresh_remote()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
