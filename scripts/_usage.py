#!/usr/bin/env python3
"""_usage.py - usage-telemetrie voor de retrieval-feedbackloop.

Registreert welke documenten de retrieval-hook injecteert en welke daarvan in
de sessie daadwerkelijk gebruikt worden (aangehaald in assistant-tekst of
geraakt door tool-calls). Dat gebruikssignaal voedt:

- de ranking (_rank.usage_factor: een warm document krijgt een boost);
- de staleness-check (een recent gebruikt artikel is niet staal, hoe oud
  zijn updated-datum ook is - gebruiksdecay in plaats van louter leeftijd).

Eigen sqlite-database ``<vault>/.claude/kb-usage.db``, bewust LOS van
kb-index.db: de index wordt bij modelwissels en rebuilds weggegooid en
usage-geschiedenis moet dat overleven. Stdlib-only (geen sqlite-vec).

Fail-open op elke route: telemetrie mag een hook nooit blokkeren; een
gemiste registratie is een miss, geen breuk. Gegate op de
``usage_telemetry``-toggle in kennisbank-settings.json (default aan).

Tabellen:
    usage(stem PK, injected, used, last_injected, last_used)
    pending(session_id, stem, ts) - injecties die nog op hun einde-sessie
        transcript-scan wachten (kb-usage-scan.py, SessionEnd).
"""
from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

DB_NAME = "kb-usage.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    stem TEXT PRIMARY KEY,
    injected INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    last_injected TEXT,
    last_used TEXT
);
CREATE TABLE IF NOT EXISTS pending (
    session_id TEXT NOT NULL,
    stem TEXT NOT NULL,
    ts TEXT,
    PRIMARY KEY (session_id, stem)
);
"""


def db_path() -> Path:
    return vault_root() / ".claude" / DB_NAME


def _connect():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=5.0)
    conn.executescript(_SCHEMA)
    return conn


def enabled() -> bool:
    """Toggle-gate; fail-open naar True (telemetrie is passief en lokaal)."""
    try:
        import _settings
        return bool(_settings.get("usage_telemetry", True))
    except Exception:
        return True


def log_injected(stems, session_id: str = "", today: str | None = None) -> int:
    """Registreer geinjecteerde stems (+pending voor de transcript-scan).

    Returns het aantal geregistreerde stems; 0 bij uit/fout (fail-open).
    """
    if not stems or not enabled():
        return 0
    day = today or date.today().isoformat()
    try:
        with closing(_connect()) as conn, conn:
            for stem in stems:
                conn.execute(
                    "INSERT INTO usage(stem, injected, last_injected) VALUES(?,1,?) "
                    "ON CONFLICT(stem) DO UPDATE SET injected=injected+1, last_injected=?",
                    (stem, day, day))
                if session_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO pending(session_id, stem, ts) VALUES(?,?,?)",
                        (session_id, stem, day))
        return len(stems)
    except Exception:
        return 0


def mark_used(stems, today: str | None = None) -> int:
    """Registreer daadwerkelijk gebruik. Returns aantal; 0 bij fout."""
    if not stems or not enabled():
        return 0
    day = today or date.today().isoformat()
    try:
        with closing(_connect()) as conn, conn:
            for stem in stems:
                conn.execute(
                    "INSERT INTO usage(stem, used, last_used) VALUES(?,1,?) "
                    "ON CONFLICT(stem) DO UPDATE SET used=used+1, last_used=?",
                    (stem, day, day))
        return len(stems)
    except Exception:
        return 0


def pending_for(session_id: str) -> list:
    """Stems die deze sessie geinjecteerd zijn en op de scan wachten."""
    if not session_id:
        return []
    try:
        with closing(_connect()) as conn, conn:
            rows = conn.execute(
                "SELECT stem FROM pending WHERE session_id = ?", (session_id,)).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def clear_pending(session_id: str) -> None:
    if not session_id:
        return
    try:
        with closing(_connect()) as conn, conn:
            conn.execute("DELETE FROM pending WHERE session_id = ?", (session_id,))
    except Exception:
        pass


def last_used_of(stem: str) -> str:
    """ISO-datum van laatste gebruik, of '' (onbekend/fout)."""
    try:
        with closing(_connect()) as conn, conn:
            row = conn.execute(
                "SELECT last_used FROM usage WHERE stem = ?", (stem,)).fetchone()
        return row[0] or "" if row else ""
    except Exception:
        return ""


def all_last_used() -> dict:
    """{stem: last_used_iso} voor alle ooit-gebruikte documenten."""
    try:
        with closing(_connect()) as conn, conn:
            rows = conn.execute(
                "SELECT stem, last_used FROM usage WHERE last_used IS NOT NULL").fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}
