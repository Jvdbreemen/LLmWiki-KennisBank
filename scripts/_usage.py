#!/usr/bin/env python3
"""_usage.py - usage-telemetrie voor de retrieval-feedbackloop.

Registreert welke documenten de retrieval-hook injecteert en welke daarvan in
de sessie daadwerkelijk gebruikt worden (geraakt door tool-calls; assistant-
tekst telt bewust niet mee). Dat gebruikssignaal voedt:

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
    usage(stem PK, injected, used, noise, last_injected, last_used, last_noise)
    pending(session_id, stem, ts) - injecties die nog op hun einde-sessie
        transcript-scan wachten (kb-usage-scan.py, SessionEnd).

Het noise-signaal (TASK-17, yesmem-les) is MENS-GATED: alleen een expliciete
menselijke markering (kb-noise.py) verhoogt de teller. Geen judge, geen
autonome down-weight; de ranking-penalty is deterministisch en begrensd
(_rank.noise_factor).
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

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
CREATE TABLE IF NOT EXISTS neighbor_log (
    day TEXT PRIMARY KEY,
    n INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS exposures (
    exposure_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    item_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    rank INTEGER,
    query TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    retrieval_kind TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_exposures_session_task
    ON exposures(session_id, task_id, ts);
CREATE TABLE IF NOT EXISTS use_events (
    use_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    item_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    ts TEXT NOT NULL,
    evidence_kind TEXT NOT NULL,
    evidence_ref TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_use_events_session_task
    ON use_events(session_id, task_id, ts);
"""


def db_path() -> Path:
    return vault_root() / ".claude" / DB_NAME


def _connect():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=5.0)
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn) -> None:
    """In-place schema-migratie: noise-kolommen op een bestaande usage-tabel.
    CREATE IF NOT EXISTS raakt bestaande tabellen niet, dus nieuwe kolommen
    komen via ALTER. Idempotent en fail-open."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(usage)")}
        if "noise" not in cols:
            conn.execute("ALTER TABLE usage ADD COLUMN noise INTEGER NOT NULL DEFAULT 0")
        if "last_noise" not in cols:
            conn.execute("ALTER TABLE usage ADD COLUMN last_noise TEXT")
    except Exception:
        pass


def enabled() -> bool:
    """Toggle-gate; fail-open naar True (telemetrie is passief en lokaal).

    KB_USAGE_DISABLE overrides the settings toggle: an eval run (kb-eval
    sets it unconditionally) must never count as usage, or the measurement
    pollutes the ranking signal it is measuring."""
    if os.environ.get("KB_USAGE_DISABLE"):
        return False
    try:
        import _settings
        return bool(_settings.get("usage_telemetry", True))
    except Exception:
        return True


def log_injected(stems, session_id: str = "", today: str | None = None,
                 neighbor_stems=()) -> int:
    """Registreer geinjecteerde stems (+pending voor de transcript-scan).

    ``neighbor_stems``: de subset die als graafbuur-expansie is geinjecteerd
    (TASK-87). Wordt per dag geteld in neighbor_log zodat doctor.sh kan tonen
    of de expansie daadwerkelijk iets oplevert — de stil-leeg-guard uit
    TASK-15: een gesloten mechanisme dat maandenlang 0 teruggeeft hoort
    zichtbaar te zijn, niet onzichtbaar.

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
            nb = len([s for s in (neighbor_stems or ()) if s in set(stems)])
            if nb:
                conn.execute(
                    "INSERT INTO neighbor_log(day, n) VALUES(?,?) "
                    "ON CONFLICT(day) DO UPDATE SET n=n+?", (day, nb, nb))
        return len(stems)
    except Exception:
        return 0


def log_exposures(items, *, session_id: str = "", task_id: str = "",
                  query: str = "", ts: str = "", source_id: str = "",
                  retrieval_kind: str = "") -> int:
    """Persist ranked layer exposures; unlike pending, this survives cleanup."""
    if not items or not session_id or not enabled():
        return 0
    import hashlib
    ts = ts or date.today().isoformat()
    try:
        with closing(_connect()) as conn, conn:
            count = 0
            for item in items:
                item_id = str(item.get("item_id") or item.get("id") or "")
                layer = str(item.get("layer") or "")
                if not item_id or not layer:
                    continue
                rank = item.get("rank")
                sid = str(item.get("source_id") or source_id or "")
                item_query = str(item.get("query") or query or "")
                item_ts = str(item.get("ts") or ts)
                key = "|".join((session_id, task_id, item_id, layer,
                                str(rank if rank is not None else ""), item_query, item_ts))
                exposure_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT OR IGNORE INTO exposures(exposure_id, session_id, task_id, "
                    "item_id, layer, rank, query, ts, source_id, retrieval_kind) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (exposure_id, session_id, task_id, item_id, layer, rank,
                     item_query, item_ts, sid,
                     str(item.get("retrieval_kind") or retrieval_kind or "")))
                count += 1
        return count
    except Exception:
        return 0


def log_use_evidence(items, *, session_id: str = "", task_id: str = "",
                     ts: str = "", evidence_kind: str = "tool_use",
                     evidence_ref: str = "") -> int:
    """Persist session-bound read/use evidence separately from exposure."""
    if not items or not session_id or not enabled():
        return 0
    import hashlib
    ts = ts or date.today().isoformat()
    try:
        with closing(_connect()) as conn, conn:
            count = 0
            for item in items:
                item_id = str(item.get("item_id") or item.get("id") or "")
                layer = str(item.get("layer") or "")
                if not item_id or not layer:
                    continue
                item_task = str(item.get("task_id") or task_id or "")
                item_ts = str(item.get("ts") or ts)
                kind = str(item.get("evidence_kind") or evidence_kind or "tool_use")
                reference = str(item.get("evidence_ref") or evidence_ref or "")
                key = "|".join((session_id, item_task, item_id, layer,
                                item_ts, kind, reference))
                use_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT OR IGNORE INTO use_events(use_id, session_id, task_id, "
                    "item_id, layer, ts, evidence_kind, evidence_ref) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (use_id, session_id, item_task, item_id, layer, item_ts,
                     kind, reference))
                count += 1
        return count
    except Exception:
        return 0


def use_evidence_for(session_id: str, *, task_id: str | None = None) -> list[dict]:
    """Return session-bound use evidence; fail-open for old usage databases."""
    if not session_id or not enabled():
        return []
    try:
        with closing(_connect()) as conn:
            columns = ("use_id, session_id, task_id, item_id, layer, ts, "
                       "evidence_kind, evidence_ref")
            if task_id is None:
                rows = conn.execute(
                    f"SELECT {columns} FROM use_events WHERE session_id=? "
                    "ORDER BY ts, use_id", (session_id,)).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {columns} FROM use_events WHERE session_id=? AND task_id=? "
                    "ORDER BY ts, use_id", (session_id, task_id)).fetchall()
        keys = ("use_id", "session_id", "task_id", "item_id", "layer", "ts",
                "evidence_kind", "evidence_ref")
        return [dict(zip(keys, row)) for row in rows]
    except Exception:
        return []


def exposures_for(session_id: str, *, task_id: str | None = None) -> list[dict]:
    if not session_id or not enabled():
        return []
    try:
        with closing(_connect()) as conn:
            if task_id is None:
                rows = conn.execute(
                    "SELECT exposure_id, session_id, task_id, item_id, layer, rank, "
                    "query, ts, source_id, retrieval_kind FROM exposures "
                    "WHERE session_id=? ORDER BY ts, rank, exposure_id", (session_id,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT exposure_id, session_id, task_id, item_id, layer, rank, "
                    "query, ts, source_id, retrieval_kind FROM exposures "
                    "WHERE session_id=? AND task_id=? ORDER BY ts, rank, exposure_id",
                    (session_id, task_id)).fetchall()
        keys = ("exposure_id", "session_id", "task_id", "item_id", "layer", "rank",
                "query", "ts", "source_id", "retrieval_kind")
        return [dict(zip(keys, row)) for row in rows]
    except Exception:
        return []


def exposures_from_context(context: str, *, query: str = "") -> list[dict]:
    """Normalize injected wiki/memory bullets into exposure records."""
    layer = ""
    ranks = {"wiki": 0, "memory": 0, "source": 0, "experience": 0}
    items = []
    for line in str(context or "").splitlines():
        lower = line.lower()
        if "wiki" in lower and line.rstrip().endswith(":"):
            layer = "wiki"
        elif ("geheugen" in lower or "memory" in lower) and line.rstrip().endswith(":"):
            layer = "memory"
        elif "source" in lower and line.rstrip().endswith(":"):
            layer = "source"
        elif "experience" in lower and line.rstrip().endswith(":"):
            layer = "experience"
        match = re.search(r"\[\[([^\[\]|#]+)", line)
        if not match or not layer:
            continue
        ranks[layer] += 1
        items.append({"item_id": match.group(1), "layer": layer,
                      "rank": ranks[layer], "query": query})
    return items


def neighbor_injected(days: int = 30) -> int:
    """Aantal als graafbuur geinjecteerde entries in de laatste ``days`` dagen.
    Fail-open -> 0 (ook op een oude db zonder neighbor_log-tabel)."""
    try:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        with closing(_connect()) as conn:
            row = conn.execute(
                "SELECT COALESCE(sum(n), 0) FROM neighbor_log WHERE day >= ?",
                (cutoff,)).fetchone()
            return int(row[0] or 0)
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


def mark_noise(stems, today: str | None = None) -> int:
    """Registreer een expliciete mens-markering 'dit was ruis in mijn context'.
    Returns aantal; 0 bij uit/fout (fail-open)."""
    if not stems or not enabled():
        return 0
    day = today or date.today().isoformat()
    try:
        with closing(_connect()) as conn, conn:
            for stem in stems:
                conn.execute(
                    "INSERT INTO usage(stem, noise, last_noise) VALUES(?,1,?) "
                    "ON CONFLICT(stem) DO UPDATE SET noise=noise+1, last_noise=?",
                    (stem, day, day))
        return len(stems)
    except Exception:
        return 0


def noise_of(stem: str) -> tuple[int, int]:
    """(noise, injected) voor een stem; (0, 0) bij onbekend/fout."""
    try:
        with closing(_connect()) as conn, conn:
            row = conn.execute(
                "SELECT noise, injected FROM usage WHERE stem = ?", (stem,)).fetchone()
        return (row[0] or 0, row[1] or 0) if row else (0, 0)
    except Exception:
        return (0, 0)


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


def stats_for(stems) -> dict:
    """{stem: {"last_used": str, "noise": int, "injected": int}} in EEN verbinding.

    last_used_of() en noise_of() openen elk een eigen verbinding per stem. Op de
    hot path worden ze per treffer aangeroepen tijdens het herwegen, wat bij zes
    treffers al twaalf opens kost. Deze batch-variant doet er een.

    Onbekende stems ontbreken in het resultaat; de aanroeper vult defaults in.
    """
    stems = [s for s in stems if s]
    if not stems:
        return {}
    try:
        placeholders = ",".join("?" for _ in stems)
        with closing(_connect()) as conn, conn:
            rows = conn.execute(
                f"SELECT stem, last_used, noise, injected FROM usage "
                f"WHERE stem IN ({placeholders})", tuple(stems)).fetchall()
        return {r[0]: {"last_used": r[1] or "", "noise": r[2] or 0, "injected": r[3] or 0}
                for r in rows}
    except Exception:
        return {}


def all_last_used() -> dict:
    """{stem: last_used_iso} voor alle ooit-gebruikte documenten."""
    try:
        with closing(_connect()) as conn, conn:
            rows = conn.execute(
                "SELECT stem, last_used FROM usage WHERE last_used IS NOT NULL").fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}
