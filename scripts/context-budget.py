#!/usr/bin/env python3
"""Progressieve context-budgetten voor KennisBank-sessies (L0-L3).

Laadt vault-context in lagen: elke hogere laag is een superset van de lagere.

L0 — identiteit:  eerste ~40 regels van <vault>/CLAUDE.md
L1 — actief:      L0 + recente sessienamen, wiki-statustellingen, open loops
L2 — relevant:    L0 + L1 + zoekresultaten via kb-search.py (vereist --query)
L3 — volledig:    L0 + L1 + L2 + volledige artikelteksten

Gebruik:
    python3 context-budget.py [--level N] [--query "zoekterm"] [--top N]

Omgevingsvariabelen:
    KB_CONTEXT_LEVEL   Standaard level (0..3), default 1
    KENNISBANK_VAULT   Vaultpad, default ~/KennisBank
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Topniveau import-patroon: scripts/ zelf op sys.path zodat onderlinge imports werken
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _vaultpath import vault_root  # noqa: E402


# ---------------------------------------------------------------------------
# Pure core — geen I/O, geïnjecteerde state, volledig testbaar zonder vault
# ---------------------------------------------------------------------------

_LAYERS = ["identity", "active", "relevant", "bodies"]


def select_layers(level: int, state: dict) -> dict:
    """Geef alleen de lagen terug die horen bij *level*.

    Parameters
    ----------
    level:
        Gewenst context-niveau. Wordt geclamped naar 0..3.
        0 -> identity
        1 -> identity + active
        2 -> identity + active + relevant
        3 -> identity + active + relevant + bodies
    state:
        Dict dat de beschikbare lagen bevat. Ontbrekende sleutels worden
        stilzwijgend weggelaten (nooit een crash).

    Returns
    -------
    dict met uitsluitend de sleutels die horen bij *level*.
    """
    level = max(0, min(3, level))
    allowed = _LAYERS[: level + 1]
    return {k: state[k] for k in allowed if k in state}


# ---------------------------------------------------------------------------
# State-assemblage — echte vault-lezingen
# ---------------------------------------------------------------------------

def _read_identity(vault: Path, lines: int = 40) -> str | None:
    """Eerste *lines* regels van <vault>/CLAUDE.md, of None als afwezig."""
    p = vault / "CLAUDE.md"
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return "\n".join(text.splitlines()[:lines])
    except OSError:
        return None


def _read_active(vault: Path) -> dict:
    """Lichtgewicht actieve-status scan.

    Leest:
    - namen van recente sessiebestanden (01-raw/sessies/)
    - wiki-statustellingen per status-label
    - open-loops stub (eenvoudige grep op 'open-loop' in sessielogs)
    Alle reads zijn fail-soft.
    """
    result: dict = {}

    # Recente sessies (laatste 10, alleen filenames)
    sessies_dir = vault / "01-raw" / "sessies"
    recent_sessions: list[str] = []
    if sessies_dir.exists():
        try:
            files = sorted(
                sessies_dir.glob("*.md"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )[:10]
            recent_sessions = [f.name for f in files]
        except OSError:
            pass
    result["recent_sessions"] = recent_sessions

    # Wiki-statustellingen
    wiki_dir = vault / "02-wiki"
    status_counts: dict[str, int] = {}
    if wiki_dir.exists():
        try:
            status_re = re.compile(r"^status:\s*(\S+)", re.MULTILINE)
            for md in wiki_dir.glob("*.md"):
                try:
                    chunk = md.read_text(encoding="utf-8", errors="replace")[:500]
                    m = status_re.search(chunk)
                    if m:
                        label = m.group(1)
                        status_counts[label] = status_counts.get(label, 0) + 1
                except OSError:
                    pass
        except OSError:
            pass
    result["status_counts"] = status_counts

    # Open-loops: eenvoudige grep op recente sessielogs
    open_loops: list[str] = []
    if sessies_dir.exists():
        try:
            loop_re = re.compile(r"open[- ]loop[:\s]+(.+)", re.IGNORECASE)
            for md in sorted(
                sessies_dir.glob("*.md"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )[:5]:
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                    for m in loop_re.finditer(text):
                        item = m.group(1).strip()[:80]
                        if item and item not in open_loops:
                            open_loops.append(item)
                except OSError:
                    pass
        except OSError:
            pass
    result["open_loops"] = open_loops

    return result


def _run_kb_search(query: str, top_n: int) -> list[dict]:
    """Roep kb-search.py aan als subprocess en geef de JSON-lijst terug."""
    scripts_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    kb_search = scripts_dir / "kb-search.py"
    if not kb_search.exists():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(kb_search), query, "--top", str(top_n)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def _read_bodies(vault: Path, relevant: list[dict]) -> dict[str, str]:
    """Lees volledige artikelteksten voor de paden in *relevant*."""
    bodies: dict[str, str] = {}
    for item in relevant:
        path_str = item.get("path", "")
        if not path_str:
            continue
        # pad kan absoluut of relatief t.o.v. vault zijn
        p = Path(path_str)
        if not p.is_absolute():
            p = vault / p
        try:
            bodies[path_str] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return bodies


def assemble_state(level: int, vault: Path, query: str | None, top_n: int) -> dict:
    """Assembleer de state-dict voor *level* vanuit de echte vault.

    Fail-soft op elk niveau: een missing vault/file levert een lege waarde,
    nooit een exception.
    """
    state: dict = {}

    # L0 altijd
    identity = _read_identity(vault)
    if identity is not None:
        state["identity"] = identity

    # L1
    if level >= 1:
        state["active"] = _read_active(vault)

    # L2 + L3
    if level >= 2 and query:
        relevant = _run_kb_search(query, top_n)
        state["relevant"] = relevant

        if level >= 3:
            state["bodies"] = _read_bodies(vault, relevant)

    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    """Lees een integer omgevingsvariabele; val terug op *default* bij ongeldige waarde."""
    try:
        return int(os.environ.get(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Progressieve context-budgetten voor KennisBank-sessies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Lagen:\n"
            "  L0  identity   eerste 40 regels CLAUDE.md\n"
            "  L1  active     + recente sessies, wiki-tellingen, open loops\n"
            "  L2  relevant   + zoekresultaten (vereist --query)\n"
            "  L3  bodies     + volledige artikelteksten\n"
        ),
    )
    default_level = _env_int("KB_CONTEXT_LEVEL", 1)
    p.add_argument(
        "--level",
        type=int,
        default=default_level,
        help=f"Context-niveau 0..3 (default: {default_level} via KB_CONTEXT_LEVEL)",
    )
    p.add_argument(
        "--query",
        default=None,
        help="Zoekterm voor L2/L3 (vereist voor relevant/bodies)",
    )
    p.add_argument(
        "--top",
        type=int,
        default=_env_int("KB_RETRIEVE_TOP_N", 3),
        help="Aantal zoekresultaten voor L2/L3 (default: 3)",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    level = max(0, min(3, args.level))
    vault = vault_root()

    state = assemble_state(level, vault, args.query, args.top)
    output = select_layers(level, state)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
