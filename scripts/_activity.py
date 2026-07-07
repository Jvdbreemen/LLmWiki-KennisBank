#!/usr/bin/env python3
"""Temporal activity recall for LLmWiki-KennisBank.

This module is deliberately stdlib-first. It turns existing local vault sources
into canonical activity events, stores them in a small SQLite index, and exposes
period/topic retrieval functions used by commands, MCP tools and tests.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _frontmatter import parse_frontmatter  # noqa: E402
from _vaultpath import vault_root  # noqa: E402


SCHEMA_VERSION = "1"
LOCAL_TZ_NAME = "Europe/Amsterdam"
try:
    LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
except ZoneInfoNotFoundError:
    # Windows Python installs do not always ship IANA tzdata. Keep the feature
    # stdlib-only and deterministic; date ranges still work, but historical DST
    # offsets cannot be represented without installing tzdata.
    LOCAL_TZ = timezone(timedelta(hours=1), LOCAL_TZ_NAME)
DB_NAME = "kb-activity.db"

SIGNAL_RE = re.compile(
    r"\b("
    r"TASK-\d+(?:\.\d+)?|ADR-\d+|release|tag|commit|push|merge|hotfix|fix|"
    r"besluit|decision|decided|blocked|geblokkeerd|done|afgerond|"
    r"MCP|Codex|Claude|OpenCode|OpenRouter|Ollama|gemma4|qwen3"
    r")\b",
    re.I,
)
TASK_RE = re.compile(r"\bTASK-\d+(?:\.\d+)?\b", re.I)
ADR_RE = re.compile(r"\bADR-\d+\b", re.I)
TAG_RE = re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b", re.I)
COMMAND_RE = re.compile(r"(?<!\w)/(?:[a-z][\w-]*)(?::[a-z][\w-]*)?", re.I)
MODEL_RE = re.compile(r"\b(?:gemma\d+(?::[\w.-]+)?|qwen3-embedding:8b|nomic-embed-text)\b", re.I)
PATH_RE = re.compile(r"(?:(?:[A-Za-z]:)?[/\\])?[A-Za-z0-9_. -]+[/\\][A-Za-z0-9_. /\\-]+\.[A-Za-z0-9]+")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


@dataclass(frozen=True)
class ActivityEvent:
    id: str
    source_kind: str
    source_path: str
    source_ref: str
    event_time: str
    captured_at: str
    timezone: str
    actor: str
    agent: str
    project: str
    repo: str
    activity_kind: str
    title: str
    summary: str
    topic_tags: list[str]
    entities: list[str]
    artifacts: list[str]
    decisions: list[str]
    confidence: float
    provenance_span: str
    unknown_time: bool = False

    def to_row(self) -> dict:
        row = asdict(self)
        for key in ("topic_tags", "entities", "artifacts", "decisions"):
            row[f"{key}_json"] = json.dumps(row.pop(key), ensure_ascii=False)
        row["unknown_time"] = 1 if self.unknown_time else 0
        row["event_date"] = self.event_time[:10] if self.event_time else ""
        row["search_blob"] = " ".join(
            str(x)
            for x in (
                self.title,
                self.summary,
                " ".join(self.topic_tags),
                " ".join(self.entities),
                " ".join(self.artifacts),
                " ".join(self.decisions),
                self.source_ref,
                self.project,
                self.repo,
            )
        )
        return row

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict) -> "ActivityEvent":
        data = dict(row)
        for key in ("topic_tags", "entities", "artifacts", "decisions"):
            raw = data.pop(f"{key}_json", "[]")
            try:
                data[key] = json.loads(raw or "[]")
            except Exception:
                data[key] = []
        data.pop("event_date", None)
        data.pop("search_blob", None)
        data["unknown_time"] = bool(data.get("unknown_time", False))
        return cls(**data)

    def as_public_dict(self) -> dict:
        data = asdict(self)
        data["source"] = {
            "kind": self.source_kind,
            "path": self.source_path,
            "ref": self.source_ref,
            "span": self.provenance_span,
        }
        return data


@dataclass(frozen=True)
class TemporalRange:
    start: str
    end_exclusive: str
    label: str
    granularity: str
    timezone: str
    confidence: float
    original_text: str
    topic: str = ""
    error: str = ""
    suggestions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.error

    def to_dict(self) -> dict:
        data = asdict(self)
        data["suggestions"] = list(self.suggestions)
        return data


def activity_db_path(vault: Path | None = None) -> Path:
    root = Path(vault) if vault is not None else vault_root()
    return root / ".claude" / DB_NAME


def stable_id(*parts: object) -> str:
    blob = "\x1f".join(str(p) for p in parts)
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()[:24]


def _norm_ws(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit]


def _read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    if limit is not None:
        return data[:limit]
    return data


def _rel(vault: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(vault.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _file_dt(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=LOCAL_TZ)


def _dt_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ).isoformat(timespec="seconds")


def _date_start(d: date, tz: ZoneInfo = LOCAL_TZ) -> datetime:
    return datetime.combine(d, dtime.min, tzinfo=tz)


def _parse_dt(value: object, *, default: datetime | None = None) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(LOCAL_TZ), False
    s = str(value or "").strip()
    if not s:
        return (default or datetime.now(LOCAL_TZ)), True
    s = s.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d-%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=LOCAL_TZ), False
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(LOCAL_TZ), False
    except ValueError:
        pass
    try:
        d = date.fromisoformat(s[:10])
        return _date_start(d), False
    except ValueError:
        return (default or datetime.now(LOCAL_TZ)), True


def _dt_from_filename(path: Path) -> tuple[datetime, bool]:
    name = path.stem
    m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})(?:[T_-]?(\d{2})[-:]?(\d{2})[-:]?(\d{2})?)?", name)
    if not m:
        return _file_dt(path), True
    y, mo, d, hh, mm, ss = m.groups()
    try:
        dt = datetime(
            int(y),
            int(mo),
            int(d),
            int(hh or 0),
            int(mm or 0),
            int(ss or 0),
            tzinfo=LOCAL_TZ,
        )
        return dt, False
    except ValueError:
        return _file_dt(path), True


def _title_from_markdown(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("---", ">")):
            return _norm_ws(stripped, 90)
    return fallback


def _first_summary(body: str, max_lines: int = 4) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip(" -*\t")
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return _norm_ws(" ".join(lines), 900)


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item or "").strip()
        if not s:
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def extract_entities(text: str, path: str = "") -> list[str]:
    candidates: list[str] = []
    candidates.extend(m.group(0).upper() for m in TASK_RE.finditer(text))
    candidates.extend(m.group(0).upper() for m in ADR_RE.finditer(text))
    candidates.extend(m.group(0) for m in TAG_RE.finditer(text))
    candidates.extend(m.group(0) for m in COMMAND_RE.finditer(text))
    candidates.extend(m.group(0) for m in MODEL_RE.finditer(text))
    candidates.extend(m.group(1) for m in WIKILINK_RE.finditer(text))
    for raw in re.findall(r"\b(?:Codex|Claude Code|Claude|OpenCode|OpenRouter|Ollama|MCP|KennisBank|Kluis|ADR kit|LLmWiki)\b", text, re.I):
        candidates.append(raw)
    p = path.replace("\\", "/")
    for part in p.split("/"):
        if part.lower() in {"adr-kit", "llmwiki-kennisbank", "otgw-firmware", "kluis"}:
            candidates.append(part)
    return _dedupe(candidates)


def extract_artifacts(text: str) -> list[str]:
    paths = [m.group(0).strip(" .,;:)") for m in PATH_RE.finditer(text)]
    paths.extend(x.strip("`") for x in re.findall(r"`([^`]+\.(?:py|md|json|toml|db|sh))`", text))
    return _dedupe(paths)


def extract_topics(text: str, path: str = "") -> list[str]:
    entities = extract_entities(text, path)
    topics: list[str] = list(entities)
    for word in re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{3,}\b", text):
        lower = word.lower()
        if lower in {
            "with",
            "from",
            "that",
            "this",
            "voor",
            "naar",
            "zijn",
            "wordt",
            "activity",
            "temporal",
            "memory",
        }:
            continue
        if word[:1].isupper() or "-" in word or lower in {"mcp", "codex", "openrouter", "ollama", "weeklog", "timeline"}:
            topics.append(word)
    return _dedupe(topics)[:32]


def classify_activity(text: str, fallback: str = "activity") -> str:
    t = text.lower()
    if "release" in t or "tag " in t or TAG_RE.search(text):
        return "release"
    if "commit" in t or "push" in t or "merge" in t:
        return "commit"
    if TASK_RE.search(text) or "backlog" in t:
        return "task_change"
    if "besluit" in t or "decision" in t or "decided" in t or "adr-" in t:
        return "decision"
    if "blocked" in t or "geblokkeerd" in t:
        return "blocked"
    if "fix" in t or "hotfix" in t or "hersteld" in t:
        return "fix"
    if "research" in t or "onderzoek" in t:
        return "external_research"
    return fallback


def state_for_event(event: ActivityEvent) -> str:
    text = f"{event.activity_kind} {event.title} {event.summary}".lower()
    if "release" in text or TAG_RE.search(text):
        return "released"
    if "blocked" in text or "geblokkeerd" in text:
        return "blocked"
    if "fix" in text or "hotfix" in text or "hersteld" in text:
        return "fixed"
    if "supersede" in text or "vervang" in text:
        return "superseded"
    if "decision" in text or "besluit" in text or "adr-" in text:
        return "changed"
    return "introduced"


def _event(
    *,
    vault: Path,
    path: Path,
    source_kind: str,
    activity_kind: str,
    title: str,
    summary: str,
    event_time: datetime,
    captured_at: datetime,
    unknown_time: bool = False,
    line_no: int | None = None,
    confidence: float = 0.75,
    actor: str = "user",
    agent: str = "",
    project: str = "",
    repo: str = "",
) -> ActivityEvent:
    rel = _rel(vault, path)
    span = f"L{line_no}" if line_no else "file"
    source_ref = f"{rel}#{span}"
    body = f"{title} {summary}"
    return ActivityEvent(
        id=stable_id(source_kind, rel, span, activity_kind, _dt_iso(event_time), _norm_ws(summary, 160)),
        source_kind=source_kind,
        source_path=rel,
        source_ref=source_ref,
        event_time=_dt_iso(event_time),
        captured_at=_dt_iso(captured_at),
        timezone=LOCAL_TZ_NAME,
        actor=actor,
        agent=agent,
        project=project,
        repo=repo,
        activity_kind=activity_kind,
        title=_norm_ws(title, 160),
        summary=_norm_ws(summary, 1200),
        topic_tags=extract_topics(body, rel),
        entities=extract_entities(body, rel),
        artifacts=extract_artifacts(body),
        decisions=[_norm_ws(summary, 300)] if activity_kind == "decision" else [],
        confidence=float(confidence),
        provenance_span=span,
        unknown_time=unknown_time,
    )


def iter_session_events(vault: Path) -> Iterable[ActivityEvent]:
    root = vault / "01-raw" / "sessies"
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.md")):
        try:
            text = _read_text(path)
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        fallback, unknown = _dt_from_filename(path)
        event_dt, time_unknown = _parse_dt(
            fm.get("date") or fm.get("created") or fm.get("event_time"),
            default=fallback,
        )
        unknown = unknown and time_unknown
        captured = _file_dt(path)
        title = str(fm.get("title") or _title_from_markdown(body, path.stem))
        summary = _first_summary(body)
        project = str(fm.get("project") or fm.get("repo") or "")
        yield _event(
            vault=vault,
            path=path,
            source_kind="raw_session",
            activity_kind="session",
            title=title,
            summary=summary,
            event_time=event_dt,
            captured_at=captured,
            unknown_time=unknown,
            confidence=0.82 if not unknown else 0.45,
            project=project,
            repo=project,
        )
        for idx, line in enumerate(body.splitlines(), start=1):
            stripped = _norm_ws(line, 500)
            if not stripped or not SIGNAL_RE.search(stripped):
                continue
            kind = classify_activity(stripped, fallback="session_signal")
            yield _event(
                vault=vault,
                path=path,
                source_kind="raw_session",
                activity_kind=kind,
                title=stripped[:100],
                summary=stripped,
                event_time=event_dt,
                captured_at=captured,
                unknown_time=unknown,
                line_no=idx,
                confidence=0.78 if not unknown else 0.42,
                project=project,
                repo=project,
            )


def iter_transcript_events(vault: Path) -> Iterable[ActivityEvent]:
    root = vault / "01-raw" / "transcripts"
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.jsonl")):
        captured = _file_dt(path)
        fallback, unknown = _dt_from_filename(path)
        emitted = 0
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for idx, raw in enumerate(lines, start=1):
            if emitted >= 80:
                break
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            ts = obj.get("timestamp") or obj.get("created_at") or obj.get("time")
            event_dt, time_unknown = _parse_dt(ts, default=fallback)
            message = obj.get("message") or obj.get("text") or obj.get("content") or ""
            if isinstance(message, dict):
                message = json.dumps(message, ensure_ascii=False)
            if isinstance(message, list):
                message = " ".join(str(x) for x in message)
            message = _norm_ws(str(message), 900)
            if not message:
                continue
            role = str(obj.get("role") or obj.get("type") or "transcript")
            if not SIGNAL_RE.search(message) and role.lower() not in {"tool_use", "assistant", "user"}:
                continue
            emitted += 1
            kind = classify_activity(message, fallback="tool_use" if "tool" in role.lower() else "transcript_message")
            yield _event(
                vault=vault,
                path=path,
                source_kind="transcript",
                activity_kind=kind,
                title=message[:100],
                summary=message,
                event_time=event_dt,
                captured_at=captured,
                unknown_time=unknown and time_unknown,
                line_no=idx,
                confidence=0.72 if not (unknown and time_unknown) else 0.4,
                actor=role,
                agent=str(obj.get("agent") or ""),
            )


def iter_memory_events(vault: Path) -> Iterable[ActivityEvent]:
    root = vault / "09-memory"
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.md")):
        if "/archive/" in path.as_posix().lower():
            continue
        try:
            text = _read_text(path)
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        fallback, unknown = _dt_from_filename(path)
        event_dt, time_unknown = _parse_dt(
            fm.get("valid_from") or fm.get("created") or fm.get("captured_at"),
            default=fallback,
        )
        captured, _ = _parse_dt(fm.get("captured_at") or fm.get("created"), default=_file_dt(path))
        title = str(fm.get("title") or _title_from_markdown(body, path.stem))
        memory_type = str(fm.get("memory_type") or fm.get("type") or "memory")
        status = str(fm.get("status") or "")
        summary = _first_summary(body) or title
        yield _event(
            vault=vault,
            path=path,
            source_kind="memory",
            activity_kind="memory_capture",
            title=title,
            summary=f"{memory_type} {status} {summary}".strip(),
            event_time=event_dt,
            captured_at=captured,
            unknown_time=unknown and time_unknown,
            confidence=0.8 if not (unknown and time_unknown) else 0.45,
            actor=str(fm.get("actor") or "agent"),
            agent=str(fm.get("agent") or ""),
            project=str(fm.get("project") or ""),
            repo=str(fm.get("repo") or ""),
        )


def iter_wiki_events(vault: Path) -> Iterable[ActivityEvent]:
    root = vault / "02-wiki"
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.md")):
        try:
            text = _read_text(path)
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        fallback = _file_dt(path)
        event_dt, unknown = _parse_dt(fm.get("updated") or fm.get("created") or fm.get("date"), default=fallback)
        title = str(fm.get("title") or _title_from_markdown(body, path.stem))
        summary = _first_summary(body) or title
        yield _event(
            vault=vault,
            path=path,
            source_kind="wiki",
            activity_kind="wiki_update",
            title=title,
            summary=summary,
            event_time=event_dt,
            captured_at=fallback,
            unknown_time=unknown,
            confidence=0.68 if not unknown else 0.4,
            project=str(fm.get("project") or ""),
            repo=str(fm.get("repo") or ""),
        )


def iter_usage_events(vault: Path) -> Iterable[ActivityEvent]:
    db = vault / ".claude" / "kb-usage.db"
    if not db.is_file():
        return
    captured = _file_dt(db)
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            lower_cols = {c.lower(): c for c in cols}
            time_col = next((lower_cols[c] for c in ("created_at", "used_at", "timestamp", "time") if c in lower_cols), None)
            text_col = next((lower_cols[c] for c in ("query", "title", "snippet", "memory_title", "path") if c in lower_cols), None)
            if not text_col:
                continue
            selected = [text_col] + ([time_col] if time_col else [])
            sql = f"SELECT {', '.join(selected)} FROM {table} LIMIT 500"
            for idx, row in enumerate(conn.execute(sql).fetchall(), start=1):
                text = _norm_ws(str(row[0] or ""), 700)
                if not text:
                    continue
                event_dt, unknown = _parse_dt(row[1] if time_col and len(row) > 1 else "", default=captured)
                yield _event(
                    vault=vault,
                    path=db,
                    source_kind="usage",
                    activity_kind="memory_use",
                    title=text[:100],
                    summary=f"{table}: {text}",
                    event_time=event_dt,
                    captured_at=captured,
                    unknown_time=unknown,
                    line_no=idx,
                    confidence=0.62 if not unknown else 0.35,
                    actor="agent",
                )
    except sqlite3.Error:
        return
    finally:
        conn.close()


def iter_activity_events(vault: Path) -> Iterable[ActivityEvent]:
    yield from iter_session_events(vault)
    yield from iter_transcript_events(vault)
    yield from iter_memory_events(vault)
    yield from iter_wiki_events(vault)
    yield from iter_usage_events(vault)


def _source_files(vault: Path) -> list[Path]:
    roots = [
        vault / "01-raw" / "sessies",
        vault / "01-raw" / "transcripts",
        vault / "09-memory",
        vault / "02-wiki",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for ext in ("*.md", "*.jsonl"):
            files.extend(p for p in root.rglob(ext) if p.is_file())
    usage = vault / ".claude" / "kb-usage.db"
    if usage.is_file():
        files.append(usage)
    return sorted(set(files))


def _fingerprint(path: Path) -> tuple[int, int, str]:
    st = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            h.update(chunk)
    return int(st.st_mtime_ns), int(st.st_size), h.hexdigest()


def connect_activity_db(vault: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    path = activity_db_path(vault)
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS activity_events ("
        "id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_path TEXT NOT NULL, "
        "source_ref TEXT NOT NULL, event_time TEXT NOT NULL, captured_at TEXT NOT NULL, "
        "timezone TEXT NOT NULL, actor TEXT, agent TEXT, project TEXT, repo TEXT, "
        "activity_kind TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL, "
        "topic_tags_json TEXT NOT NULL, entities_json TEXT NOT NULL, "
        "artifacts_json TEXT NOT NULL, decisions_json TEXT NOT NULL, "
        "confidence REAL NOT NULL, provenance_span TEXT NOT NULL, unknown_time INTEGER NOT NULL, "
        "event_date TEXT NOT NULL, search_blob TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_event_time ON activity_events(event_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_captured_at ON activity_events(captured_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_kind ON activity_events(activity_kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_project ON activity_events(project)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_source ON activity_events(source_path)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS activity_entities ("
        "event_id TEXT NOT NULL, entity TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'entity', "
        "PRIMARY KEY(event_id, entity, kind))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS activity_topics ("
        "event_id TEXT NOT NULL, topic TEXT NOT NULL, match_route TEXT NOT NULL DEFAULT 'explicit', "
        "PRIMARY KEY(event_id, topic, match_route))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS activity_artifacts ("
        "event_id TEXT NOT NULL, artifact TEXT NOT NULL, PRIMARY KEY(event_id, artifact))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS source_watermarks ("
        "source_path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL, "
        "sha256 TEXT NOT NULL, indexed_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rollup_cache ("
        "cache_key TEXT PRIMARY KEY, start TEXT NOT NULL, end_exclusive TEXT NOT NULL, "
        "topic TEXT NOT NULL, source_signature TEXT NOT NULL, body_json TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS activity_fts USING fts5(id UNINDEXED, title, summary, entities, topics)")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    conn.commit()


def _delete_event(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute("DELETE FROM activity_events WHERE id=?", (event_id,))
    conn.execute("DELETE FROM activity_fts WHERE id=?", (event_id,))
    conn.execute("DELETE FROM activity_entities WHERE event_id=?", (event_id,))
    conn.execute("DELETE FROM activity_topics WHERE event_id=?", (event_id,))
    conn.execute("DELETE FROM activity_artifacts WHERE event_id=?", (event_id,))


def upsert_event(conn: sqlite3.Connection, event: ActivityEvent) -> None:
    _delete_event(conn, event.id)
    row = event.to_row()
    cols = [
        "id",
        "source_kind",
        "source_path",
        "source_ref",
        "event_time",
        "captured_at",
        "timezone",
        "actor",
        "agent",
        "project",
        "repo",
        "activity_kind",
        "title",
        "summary",
        "topic_tags_json",
        "entities_json",
        "artifacts_json",
        "decisions_json",
        "confidence",
        "provenance_span",
        "unknown_time",
        "event_date",
        "search_blob",
    ]
    conn.execute(
        f"INSERT INTO activity_events({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        tuple(row[c] for c in cols),
    )
    conn.execute(
        "INSERT INTO activity_fts(id, title, summary, entities, topics) VALUES (?, ?, ?, ?, ?)",
        (
            event.id,
            event.title,
            event.summary,
            " ".join(event.entities),
            " ".join(event.topic_tags),
        ),
    )
    for entity in event.entities:
        conn.execute(
            "INSERT OR IGNORE INTO activity_entities(event_id, entity, kind) VALUES (?, ?, ?)",
            (event.id, entity, "entity"),
        )
    for topic in event.topic_tags:
        conn.execute(
            "INSERT OR IGNORE INTO activity_topics(event_id, topic, match_route) VALUES (?, ?, ?)",
            (event.id, topic, "explicit"),
        )
    for artifact in event.artifacts:
        conn.execute(
            "INSERT OR IGNORE INTO activity_artifacts(event_id, artifact) VALUES (?, ?)",
            (event.id, artifact),
        )


def _events_for_source(vault: Path, source: Path) -> list[ActivityEvent]:
    rel = _rel(vault, source)
    if rel.startswith("01-raw/sessies/"):
        try:
            text = _read_text(source)
        except OSError:
            return []
        fm, body = parse_frontmatter(text)
        fallback, unknown = _dt_from_filename(source)
        event_dt, time_unknown = _parse_dt(
            fm.get("date") or fm.get("created") or fm.get("event_time"),
            default=fallback,
        )
        unknown = unknown and time_unknown
        captured = _file_dt(source)
        title = str(fm.get("title") or _title_from_markdown(body, source.stem))
        summary = _first_summary(body)
        project = str(fm.get("project") or fm.get("repo") or "")
        events = [
            _event(
                vault=vault,
                path=source,
                source_kind="raw_session",
                activity_kind="session",
                title=title,
                summary=summary,
                event_time=event_dt,
                captured_at=captured,
                unknown_time=unknown,
                confidence=0.82 if not unknown else 0.45,
                project=project,
                repo=project,
            )
        ]
        for idx, line in enumerate(body.splitlines(), start=1):
            stripped = _norm_ws(line, 500)
            if not stripped or not SIGNAL_RE.search(stripped):
                continue
            kind = classify_activity(stripped, fallback="session_signal")
            events.append(
                _event(
                    vault=vault,
                    path=source,
                    source_kind="raw_session",
                    activity_kind=kind,
                    title=stripped[:100],
                    summary=stripped,
                    event_time=event_dt,
                    captured_at=captured,
                    unknown_time=unknown,
                    line_no=idx,
                    confidence=0.78 if not unknown else 0.42,
                    project=project,
                    repo=project,
                )
            )
        return events
    if rel.startswith("01-raw/transcripts/"):
        captured = _file_dt(source)
        fallback, unknown = _dt_from_filename(source)
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        events = []
        emitted = 0
        for idx, raw in enumerate(lines, start=1):
            if emitted >= 80:
                break
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            ts = obj.get("timestamp") or obj.get("created_at") or obj.get("time")
            event_dt, time_unknown = _parse_dt(ts, default=fallback)
            message = obj.get("message") or obj.get("text") or obj.get("content") or ""
            if isinstance(message, dict):
                message = json.dumps(message, ensure_ascii=False)
            if isinstance(message, list):
                message = " ".join(str(x) for x in message)
            message = _norm_ws(str(message), 900)
            if not message:
                continue
            role = str(obj.get("role") or obj.get("type") or "transcript")
            if not SIGNAL_RE.search(message) and role.lower() not in {"tool_use", "assistant", "user"}:
                continue
            emitted += 1
            kind = classify_activity(message, fallback="tool_use" if "tool" in role.lower() else "transcript_message")
            events.append(
                _event(
                    vault=vault,
                    path=source,
                    source_kind="transcript",
                    activity_kind=kind,
                    title=message[:100],
                    summary=message,
                    event_time=event_dt,
                    captured_at=captured,
                    unknown_time=unknown and time_unknown,
                    line_no=idx,
                    confidence=0.72 if not (unknown and time_unknown) else 0.4,
                    actor=role,
                    agent=str(obj.get("agent") or ""),
                )
            )
        return events
    if rel.startswith("09-memory/"):
        if "/archive/" in source.as_posix().lower():
            return []
        try:
            text = _read_text(source)
        except OSError:
            return []
        fm, body = parse_frontmatter(text)
        fallback, unknown = _dt_from_filename(source)
        event_dt, time_unknown = _parse_dt(
            fm.get("valid_from") or fm.get("created") or fm.get("captured_at"),
            default=fallback,
        )
        captured, _ = _parse_dt(fm.get("captured_at") or fm.get("created"), default=_file_dt(source))
        title = str(fm.get("title") or _title_from_markdown(body, source.stem))
        memory_type = str(fm.get("memory_type") or fm.get("type") or "memory")
        status = str(fm.get("status") or "")
        summary = _first_summary(body) or title
        return [
            _event(
                vault=vault,
                path=source,
                source_kind="memory",
                activity_kind="memory_capture",
                title=title,
                summary=f"{memory_type} {status} {summary}".strip(),
                event_time=event_dt,
                captured_at=captured,
                unknown_time=unknown and time_unknown,
                confidence=0.8 if not (unknown and time_unknown) else 0.45,
                actor=str(fm.get("actor") or "agent"),
                agent=str(fm.get("agent") or ""),
                project=str(fm.get("project") or ""),
                repo=str(fm.get("repo") or ""),
            )
        ]
    if rel.startswith("02-wiki/"):
        try:
            text = _read_text(source)
        except OSError:
            return []
        fm, body = parse_frontmatter(text)
        fallback = _file_dt(source)
        event_dt, unknown = _parse_dt(fm.get("updated") or fm.get("created") or fm.get("date"), default=fallback)
        title = str(fm.get("title") or _title_from_markdown(body, source.stem))
        summary = _first_summary(body) or title
        return [
            _event(
                vault=vault,
                path=source,
                source_kind="wiki",
                activity_kind="wiki_update",
                title=title,
                summary=summary,
                event_time=event_dt,
                captured_at=fallback,
                unknown_time=unknown,
                confidence=0.68 if not unknown else 0.4,
                project=str(fm.get("project") or ""),
                repo=str(fm.get("repo") or ""),
            )
        ]
    if rel == ".claude/kb-usage.db":
        return list(iter_usage_events(vault))
    return []


def _source_signature(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT source_path, mtime_ns, size, sha256 FROM source_watermarks ORDER BY source_path"
    ).fetchall()
    return hashlib.sha256(json.dumps([tuple(r) for r in rows], sort_keys=True).encode("utf-8")).hexdigest()


def build_activity_index(
    vault: Path | None = None,
    *,
    full: bool = False,
    progress_interval: float = 300.0,
    verbose: bool = True,
) -> dict:
    root = Path(vault) if vault is not None else vault_root()
    start = time.monotonic()
    db = activity_db_path(root)
    if full and db.exists():
        db.unlink()
        for suffix in ("-wal", "-shm"):
            p = Path(str(db) + suffix)
            if p.exists():
                p.unlink()
    conn = connect_activity_db(root)
    ensure_schema(conn)
    sources = _source_files(root)
    current_rel = {_rel(root, p) for p in sources}
    stats = {
        "vault": str(root),
        "db": str(db),
        "schema_version": SCHEMA_VERSION,
        "full": bool(full),
        "sources": len(sources),
        "changed_sources": 0,
        "skipped_sources": 0,
        "events_indexed": 0,
        "events_deleted": 0,
        "elapsed_seconds": 0.0,
    }
    last_report = start
    try:
        stale_sources = [
            r[0]
            for r in conn.execute("SELECT source_path FROM source_watermarks").fetchall()
            if r[0] not in current_rel
        ]
        for rel in stale_sources:
            ids = [r[0] for r in conn.execute("SELECT id FROM activity_events WHERE source_path=?", (rel,)).fetchall()]
            for event_id in ids:
                _delete_event(conn, event_id)
            conn.execute("DELETE FROM source_watermarks WHERE source_path=?", (rel,))
            stats["events_deleted"] += len(ids)

        for idx, source in enumerate(sources, start=1):
            rel = _rel(root, source)
            mtime_ns, size, sha = _fingerprint(source)
            old = conn.execute(
                "SELECT mtime_ns, size, sha256 FROM source_watermarks WHERE source_path=?",
                (rel,),
            ).fetchone()
            unchanged = old and int(old["mtime_ns"]) == mtime_ns and int(old["size"]) == size and old["sha256"] == sha
            if unchanged and not full:
                stats["skipped_sources"] += 1
            else:
                stats["changed_sources"] += 1
                ids = [r[0] for r in conn.execute("SELECT id FROM activity_events WHERE source_path=?", (rel,)).fetchall()]
                for event_id in ids:
                    _delete_event(conn, event_id)
                events = _events_for_source(root, source)
                for event in events:
                    upsert_event(conn, event)
                conn.execute(
                    "INSERT OR REPLACE INTO source_watermarks(source_path, mtime_ns, size, sha256, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rel, mtime_ns, size, sha, _dt_iso(datetime.now(LOCAL_TZ))),
                )
                stats["events_indexed"] += len(events)
            now = time.monotonic()
            if verbose and (now - last_report >= progress_interval or idx == len(sources)):
                elapsed = now - start
                print(
                    f"activity-index: {idx}/{len(sources)} sources, "
                    f"{stats['events_indexed']} events indexed, "
                    f"{stats['skipped_sources']} unchanged, elapsed {elapsed:.1f}s, current={rel}",
                    file=sys.stderr,
                    flush=True,
                )
                last_report = now
        conn.execute("DELETE FROM rollup_cache WHERE source_signature != ?", (_source_signature(conn),))
        conn.commit()
        stats["elapsed_seconds"] = round(time.monotonic() - start, 3)
        stats["total_events"] = conn.execute("SELECT count(*) FROM activity_events").fetchone()[0]
        stats["source_signature"] = _source_signature(conn)
    finally:
        conn.close()
    return stats


MONTHS = {
    "januari": 1,
    "jan": 1,
    "februari": 2,
    "feb": 2,
    "maart": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "mei": 5,
    "may": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "augustus": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "oktober": 10,
    "october": 10,
    "okt": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "june": 6,
    "july": 7,
    "august": 8,
}
WEEKDAYS = {
    "maandag": 0,
    "monday": 0,
    "dinsdag": 1,
    "tuesday": 1,
    "woensdag": 2,
    "wednesday": 2,
    "donderdag": 3,
    "thursday": 3,
    "vrijdag": 4,
    "friday": 4,
    "zaterdag": 5,
    "saturday": 5,
    "zondag": 6,
    "sunday": 6,
}


def _now_dt(now: datetime | None = None, tz: ZoneInfo = LOCAL_TZ) -> datetime:
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _month_range(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def _parse_date_token(raw: str, tz: ZoneInfo) -> date | None:
    s = raw.strip().strip(",.")
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+|[A-Za-z]+\.|[A-Za-z]+)\s+(\d{4})$", s, re.I)
    if m:
        day, month_name, year = m.groups()
        month = MONTHS.get(month_name.rstrip(".").lower())
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", s, re.I)
    if m:
        month_name, day, year = m.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None
    return None


def _extract_topic_and_clean(text: str) -> tuple[str, str]:
    topic = ""
    cleaned = text
    m = re.search(r"\b(?:onderwerp|topic)\s+[\"']([^\"']+)[\"']", cleaned, re.I)
    if m:
        topic = m.group(1).strip()
        cleaned = (cleaned[: m.start()] + " " + cleaned[m.end() :]).strip()
    return topic, cleaned


def _mk_range(start: datetime, end: datetime, label: str, granularity: str, original: str, topic: str = "", confidence: float = 0.95) -> TemporalRange:
    return TemporalRange(
        start=_dt_iso(start),
        end_exclusive=_dt_iso(end),
        label=label,
        granularity=granularity,
        timezone=LOCAL_TZ_NAME,
        confidence=confidence,
        original_text=original,
        topic=topic,
    )


def _period_error(original: str, topic: str = "") -> TemporalRange:
    return TemporalRange(
        start="",
        end_exclusive="",
        label="invalid",
        granularity="unknown",
        timezone=LOCAL_TZ_NAME,
        confidence=0.0,
        original_text=original,
        topic=topic,
        error="Kon geen eenduidige datum of periode herkennen.",
        suggestions=("vandaag", "gisteren", "vorige week", "2026-07-03", "tussen 2026-07-01 en 2026-07-07"),
    )


def parse_period(text: str = "", *, now: datetime | None = None, tz: ZoneInfo = LOCAL_TZ, default: str = "today") -> TemporalRange:
    original = (text or "").strip()
    topic, cleaned = _extract_topic_and_clean(original)
    query = cleaned.strip() or default
    lower = query.lower()
    current = _now_dt(now, tz)
    today = current.date()
    today_start = _date_start(today, tz)

    range_patterns = (
        r"\b(?:tussen|between)\s+(.+?)\s+(?:en|and)\s+(.+)$",
        r"\b(?:van|from)\s+(.+?)\s+(?:tot|to)\s+(.+)$",
    )
    for pat in range_patterns:
        m = re.search(pat, query, re.I)
        if m:
            left, right = m.groups()
            d1 = _parse_date_token(left, tz)
            d2 = _parse_date_token(right, tz)
            if d1 and d2:
                start = _date_start(d1, tz)
                end = _date_start(d2 + timedelta(days=1), tz)
                rest = (query[: m.start()] + " " + query[m.end() :]).strip()
                topic = topic or rest
                return _mk_range(start, end, f"{d1.isoformat()}..{d2.isoformat()}", "range", original, topic)

    m = re.search(
        r"\b(?:van|from)\s+("
        + "|".join(WEEKDAYS)
        + r")\s+(?:tot|to)\s+("
        + "|".join(WEEKDAYS)
        + r")\b",
        lower,
    )
    if m:
        a, b = m.groups()
        week_start = today_start - timedelta(days=today.weekday())
        start = week_start + timedelta(days=WEEKDAYS[a])
        end = week_start + timedelta(days=WEEKDAYS[b] + 1)
        if end <= start:
            end += timedelta(days=7)
        rest = re.sub(re.escape(m.group(0)), "", lower, count=1).strip()
        topic = topic or rest
        return _mk_range(start, end, f"{a}..{b}", "range", original, topic)

    patterns = [
        (r"\b(?:vorige week|last week)\b", "previous_week"),
        (r"\b(?:deze week|this week)\b", "this_week"),
        (r"\b(?:vorige maand|last month)\b", "previous_month"),
        (r"\b(?:deze maand|this month)\b", "this_month"),
        (r"\b(?:vandaag|today)\b", "today"),
        (r"\b(?:gisteren|yesterday)\b", "yesterday"),
        (r"\b(?:eergisteren|day before yesterday)\b", "day_before_yesterday"),
    ]
    for pat, kind in patterns:
        m = re.search(pat, lower)
        if not m:
            continue
        rest = (query[: m.start()] + " " + query[m.end() :]).strip()
        topic = topic or rest
        week_start = today_start - timedelta(days=today.weekday())
        if kind == "previous_week":
            return _mk_range(week_start - timedelta(days=7), week_start, "vorige week", "week", original, topic)
        if kind == "this_week":
            return _mk_range(week_start, week_start + timedelta(days=7), "deze week", "week", original, topic)
        if kind == "previous_month":
            y = today.year
            mo = today.month - 1
            if mo == 0:
                y -= 1
                mo = 12
            start, end = _month_range(y, mo, tz)
            return _mk_range(start, end, f"{y}-{mo:02d}", "month", original, topic)
        if kind == "this_month":
            start, end = _month_range(today.year, today.month, tz)
            return _mk_range(start, end, f"{today.year}-{today.month:02d}", "month", original, topic)
        offset = {"today": 0, "yesterday": 1, "day_before_yesterday": 2}[kind]
        d = today - timedelta(days=offset)
        return _mk_range(_date_start(d, tz), _date_start(d + timedelta(days=1), tz), d.isoformat(), "day", original, topic)

    m = re.search(r"\b(?:afgelopen|laatste|last)\s+(\d{1,3})\s+(?:dagen|days)\b", lower)
    if m:
        days = max(1, min(366, int(m.group(1))))
        start = today_start - timedelta(days=days - 1)
        end = today_start + timedelta(days=1)
        rest = (query[: m.start()] + " " + query[m.end() :]).strip()
        topic = topic or rest
        return _mk_range(start, end, f"afgelopen {days} dagen", "range", original, topic, 0.9)

    m = re.search(r"\b(\d{4})-(\d{2})\b(?!-\d{2})", query)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            start, end = _month_range(y, mo, tz)
            rest = (query[: m.start()] + " " + query[m.end() :]).strip()
            topic = topic or rest
            return _mk_range(start, end, f"{y}-{mo:02d}", "month", original, topic)

    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
    if date_match:
        d = _parse_date_token(date_match.group(1), tz)
        if d:
            rest = (query[: date_match.start()] + " " + query[date_match.end() :]).strip()
            topic = topic or rest
            return _mk_range(_date_start(d, tz), _date_start(d + timedelta(days=1), tz), d.isoformat(), "day", original, topic)

    for m in re.finditer(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})\b", query, re.I):
        d = _parse_date_token(m.group(1), tz)
        if d:
            rest = (query[: m.start()] + " " + query[m.end() :]).strip()
            topic = topic or rest
            return _mk_range(_date_start(d, tz), _date_start(d + timedelta(days=1), tz), d.isoformat(), "day", original, topic)

    if re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", query):
        return TemporalRange(
            start="",
            end_exclusive="",
            label="ambiguous",
            granularity="unknown",
            timezone=LOCAL_TZ_NAME,
            confidence=0.0,
            original_text=original,
            topic=topic,
            error="Ambigue datum. Gebruik ISO-formaat YYYY-MM-DD of schrijf de maand uit.",
            suggestions=("2026-07-03", "3 juli 2026", "July 3 2026"),
        )
    return _period_error(original, topic)


def _parse_iso_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(LOCAL_TZ)


def _topic_aliases(vault: Path) -> dict[str, list[str]]:
    for path in (vault / ".claude" / "activity-topic-aliases.json", vault / "activity-topic-aliases.json"):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return {str(k).lower(): [str(x) for x in v] for k, v in data.items() if isinstance(v, list)}
    return {}


def _topic_terms(topic: str, vault: Path) -> list[str]:
    terms = [topic.strip()] if topic and topic.strip() else []
    aliases = _topic_aliases(vault)
    lower = topic.lower().strip()
    terms.extend(aliases.get(lower, []))
    for key, vals in aliases.items():
        if lower in [v.lower() for v in vals]:
            terms.append(key)
            terms.extend(vals)
    return _dedupe(terms)


def _event_match_route(event: ActivityEvent, terms: list[str]) -> str:
    if not terms:
        return "range"
    hay_entities = " ".join(event.entities + event.topic_tags).lower()
    hay = f"{event.title} {event.summary} {event.source_path} {hay_entities}".lower()
    for term in terms:
        t = term.lower()
        if t in [e.lower() for e in event.entities]:
            return "explicit_entity"
        if t in [x.lower() for x in event.topic_tags]:
            return "explicit_topic"
        if t in hay_entities:
            return "tag"
        if t in hay:
            return "fts"
    return ""


def _rows_to_events(rows: list[sqlite3.Row]) -> list[ActivityEvent]:
    return [ActivityEvent.from_row(r) for r in rows]


def query_events(
    vault: Path | None,
    period: TemporalRange,
    *,
    topic: str = "",
    project: str = "",
    limit: int = 50,
) -> tuple[list[dict], list[str]]:
    root = Path(vault) if vault is not None else vault_root()
    db = activity_db_path(root)
    warnings: list[str] = []
    if not db.is_file():
        return [], [f"activity index ontbreekt: {db}. Run build-activity-index.py --full."]
    if not period.ok:
        return [], [period.error]
    try:
        conn = connect_activity_db(root, readonly=True)
    except sqlite3.Error as e:
        return [], [f"activity index niet leesbaar: {e}"]
    terms = _topic_terms(topic or period.topic, root)
    pool_limit = max(int(limit) * 5, int(limit))
    if terms:
        pool_limit = min(max(int(limit) * 50, 1000), 10000)
    try:
        rows = conn.execute(
            "SELECT * FROM activity_events WHERE event_time >= ? AND event_time < ? "
            "ORDER BY event_time ASC, id ASC LIMIT ?",
            (period.start, period.end_exclusive, pool_limit),
        ).fetchall()
    except sqlite3.Error as e:
        conn.close()
        return [], [f"activity query faalde: {e}"]
    finally:
        try:
            conn.close()
        except Exception:
            pass
    events = _rows_to_events(rows)
    if project:
        p = project.lower()
        events = [e for e in events if p in f"{e.project} {e.repo} {e.source_path} {' '.join(e.entities)}".lower()]
    out: list[dict] = []
    for event in events:
        route = _event_match_route(event, terms)
        if terms and not route:
            continue
        item = event.as_public_dict()
        item["match_route"] = route or "range"
        item["state"] = state_for_event(event)
        out.append(item)
        if len(out) >= limit:
            break
    return out, warnings


def _summary_counts(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in events:
        kind = ev.get("activity_kind") or "activity"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _source_signature_for_period(vault: Path, start: str, end: str, topic: str) -> str:
    try:
        conn = connect_activity_db(vault, readonly=True)
        rows = conn.execute(
            "SELECT id, event_time, source_ref FROM activity_events WHERE event_time >= ? AND event_time < ? ORDER BY id",
            (start, end),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        rows = []
    return hashlib.sha256(json.dumps([tuple(r) for r in rows] + [topic], sort_keys=True).encode("utf-8")).hexdigest()


def _rollup_cache_get(vault: Path, key: str, signature: str) -> dict | None:
    try:
        conn = connect_activity_db(vault, readonly=True)
        row = conn.execute("SELECT body_json FROM rollup_cache WHERE cache_key=? AND source_signature=?", (key, signature)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _rollup_cache_put(vault: Path, key: str, period: TemporalRange, topic: str, signature: str, body: dict) -> None:
    try:
        conn = connect_activity_db(vault)
        ensure_schema(conn)
        conn.execute(
            "INSERT OR REPLACE INTO rollup_cache(cache_key, start, end_exclusive, topic, source_signature, body_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, period.start, period.end_exclusive, topic, signature, json.dumps(body, ensure_ascii=False), _dt_iso(datetime.now(LOCAL_TZ))),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def deterministic_rollup(vault: Path, period: TemporalRange, events: list[dict], topic: str = "") -> dict:
    signature = _source_signature_for_period(vault, period.start, period.end_exclusive, topic)
    key = stable_id("rollup", period.start, period.end_exclusive, topic)
    cached = _rollup_cache_get(vault, key, signature)
    if cached:
        cached["cache"] = "hit"
        return cached
    decisions = [e for e in events if e.get("activity_kind") == "decision" or e.get("decisions")]
    releases = [e for e in events if e.get("activity_kind") in {"release", "commit", "task_change"}]
    open_loops = [
        e for e in events
        if re.search(r"\b(todo|follow[- ]?up|blocked|open|wacht|later|next)\b", f"{e.get('title','')} {e.get('summary','')}", re.I)
    ]
    body = {
        "period": period.to_dict(),
        "topic": topic,
        "event_count": len(events),
        "counts": _summary_counts(events),
        "key_events": events[:12],
        "decisions": decisions[:12],
        "releases_tasks": releases[:12],
        "open_loops": open_loops[:12],
        "source_refs": _dedupe(e.get("source_ref", "") for e in events)[:50],
        "generated": "deterministic",
        "cache": "miss",
    }
    _rollup_cache_put(vault, key, period, topic, signature, body)
    return body


def what_did_i_do(
    date_or_period: str = "today",
    *,
    topic: str = "",
    project: str = "",
    max_events: int = 25,
    vault: Path | None = None,
    now: datetime | None = None,
) -> dict:
    root = Path(vault) if vault is not None else vault_root()
    period = parse_period(date_or_period, now=now, default="today")
    result_topic = topic or period.topic
    result: dict = {
        "ok": period.ok,
        "mode": "what_did_i_do",
        "period": period.to_dict(),
        "topic": result_topic,
        "project": project,
        "events": [],
        "warnings": [],
        "summary": {},
        "evidence": [],
    }
    if not period.ok:
        result["warnings"].append(period.error)
        return result
    events, warnings = query_events(root, period, topic=result_topic, project=project, limit=max_events)
    result["events"] = events
    result["warnings"].extend(warnings)
    result["summary"] = {
        "event_count": len(events),
        "counts": _summary_counts(events),
        "top_titles": [e["title"] for e in events[:5]],
    }
    result["evidence"] = _dedupe(e.get("source_ref", "") for e in events)
    result["ok"] = not bool(warnings and not events)
    return result


def timeline(
    period_text: str = "today",
    *,
    topic: str = "",
    project: str = "",
    max_events: int = 50,
    vault: Path | None = None,
    now: datetime | None = None,
) -> dict:
    result = what_did_i_do(period_text, topic=topic, project=project, max_events=max_events, vault=vault, now=now)
    result["mode"] = "timeline"
    return result


def topic_timeline(
    topic: str,
    *,
    period_text: str = "afgelopen 90 dagen",
    project: str = "",
    max_events: int = 80,
    vault: Path | None = None,
    now: datetime | None = None,
) -> dict:
    result = timeline(period_text, topic=topic, project=project, max_events=max_events, vault=vault, now=now)
    result["mode"] = "topic_timeline"
    result["topic_state_counts"] = _summary_counts([{"activity_kind": e.get("state", "")} for e in result.get("events", [])])
    return result


def weeklog(
    period_text: str = "vorige week",
    *,
    topic: str = "",
    project: str = "",
    max_events: int = 100,
    vault: Path | None = None,
    now: datetime | None = None,
) -> dict:
    root = Path(vault) if vault is not None else vault_root()
    result = what_did_i_do(period_text or "vorige week", topic=topic, project=project, max_events=max_events, vault=root, now=now)
    result["mode"] = "weeklog"
    if result["period"].get("error"):
        return result
    period = TemporalRange(**{**result["period"], "suggestions": tuple(result["period"].get("suggestions", []))})
    result["rollup"] = deterministic_rollup(root, period, result.get("events", []), topic or result.get("topic", ""))
    return result


def format_markdown(result: dict) -> str:
    mode = result.get("mode", "timeline")
    period = result.get("period", {})
    if period.get("error"):
        suggestions = ", ".join(period.get("suggestions", []))
        return f"Temporal query error: {period.get('error')}\nSuggesties: {suggestions}"
    warnings = result.get("warnings") or []
    if warnings and not result.get("events"):
        return "\n".join(["Temporal Activity Recall", *[f"- WARN: {w}" for w in warnings]])

    events = result.get("events") or []
    title = {
        "weeklog": "Weeklog",
        "what_did_i_do": "Wat deed ik",
        "topic_timeline": "Topic timeline",
    }.get(mode, "Timeline")
    lines = [f"{title}: {period.get('label', '')}".strip()]
    if result.get("topic"):
        lines.append(f"Topic: {result['topic']}")
    if warnings:
        lines.extend(f"WARN: {w}" for w in warnings)
    if not events:
        lines.append("Geen activity events gevonden voor deze periode.")
        return "\n".join(lines)
    if mode == "weeklog" and result.get("rollup"):
        rollup = result["rollup"]
        lines.append(f"Events: {rollup.get('event_count', 0)}")
        if rollup.get("counts"):
            counts = ", ".join(f"{k}={v}" for k, v in sorted(rollup["counts"].items()))
            lines.append(f"Verdeling: {counts}")
        lines.append("")
        lines.append("Belangrijkste activiteiten")
        for ev in rollup.get("key_events", [])[:10]:
            lines.append(_format_event_line(ev))
        if rollup.get("decisions"):
            lines.append("")
            lines.append("Beslissingen")
            for ev in rollup["decisions"][:8]:
                lines.append(_format_event_line(ev))
        if rollup.get("open_loops"):
            lines.append("")
            lines.append("Open loops")
            for ev in rollup["open_loops"][:8]:
                lines.append(_format_event_line(ev))
    else:
        for ev in events:
            lines.append(_format_event_line(ev))
    source_refs = result.get("evidence") or _dedupe(e.get("source_ref", "") for e in events)
    if source_refs:
        lines.append("")
        lines.append("Bronnen")
        for ref in source_refs[:12]:
            lines.append(f"- {ref}")
    return "\n".join(lines)


def _format_event_line(ev: dict) -> str:
    when = str(ev.get("event_time", ""))[:16].replace("T", " ")
    kind = ev.get("activity_kind", "activity")
    title = _norm_ws(ev.get("title", ""), 140)
    source = ev.get("source_ref") or ev.get("source", {}).get("ref", "")
    route = ev.get("match_route", "")
    suffix = f"; {route}" if route and route != "range" else ""
    return f"- {when} [{kind}] {title} ({source}{suffix})"


def index_status(vault: Path | None = None) -> dict:
    root = Path(vault) if vault is not None else vault_root()
    db = activity_db_path(root)
    status = {
        "db": str(db),
        "exists": db.is_file(),
        "ok": False,
        "schema_version": "",
        "events": 0,
        "sources": 0,
        "stale_sources": 0,
        "warnings": [],
    }
    if not db.is_file():
        status["warnings"].append("activity index ontbreekt")
        return status
    try:
        conn = connect_activity_db(root, readonly=True)
        schema = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        status["schema_version"] = schema[0] if schema else ""
        status["events"] = conn.execute("SELECT count(*) FROM activity_events").fetchone()[0]
        status["sources"] = conn.execute("SELECT count(*) FROM source_watermarks").fetchone()[0]
        current = {_rel(root, p) for p in _source_files(root)}
        stale = 0
        for row in conn.execute("SELECT source_path, mtime_ns, size, sha256 FROM source_watermarks"):
            p = root / row["source_path"]
            if not p.is_file():
                stale += 1
                continue
            mtime_ns, size, sha = _fingerprint(p)
            if int(row["mtime_ns"]) != mtime_ns or int(row["size"]) != size or row["sha256"] != sha:
                stale += 1
        indexed = {r[0] for r in conn.execute("SELECT source_path FROM source_watermarks")}
        stale += len(current - indexed)
        status["stale_sources"] = stale
        status["ok"] = status["schema_version"] == SCHEMA_VERSION and status["events"] >= 0 and stale == 0
        conn.close()
    except sqlite3.Error as e:
        status["warnings"].append(f"activity index corrupt of onleesbaar: {e}")
    return status


def eval_queries(vault: Path, eval_set: list[dict], *, now: datetime | None = None) -> dict:
    cases = []
    passed = 0
    for item in eval_set:
        mode = item.get("mode", "timeline")
        query = item.get("query") or item.get("period") or "today"
        topic = item.get("topic", "")
        if mode == "weeklog":
            result = weeklog(query, topic=topic, vault=vault, now=now)
        elif mode == "what_did_i_do":
            result = what_did_i_do(query, topic=topic, vault=vault, now=now)
        elif mode == "topic_timeline":
            result = topic_timeline(topic or query, period_text=item.get("period", "afgelopen 90 dagen"), vault=vault, now=now)
        else:
            result = timeline(query, topic=topic, vault=vault, now=now)
        ids = {e["id"] for e in result.get("events", [])}
        refs = " ".join(e.get("source_ref", "") for e in result.get("events", []))
        expected_ids = set(item.get("expected_event_ids") or [])
        expected_ref_contains = item.get("expected_ref_contains") or []
        min_events = int(item.get("min_events", 0))
        max_events = item.get("max_events")
        ok = result.get("period", {}).get("error") == item.get("expected_error", "")
        if expected_ids:
            ok = ok and expected_ids.issubset(ids)
        if expected_ref_contains:
            ok = ok and all(str(x) in refs for x in expected_ref_contains)
        if min_events:
            ok = ok and len(result.get("events", [])) >= min_events
        if max_events is not None:
            ok = ok and len(result.get("events", [])) <= int(max_events)
        if item.get("require_provenance", True):
            ok = ok and all(e.get("source_ref") or e.get("source", {}).get("ref") for e in result.get("events", []))
        if ok:
            passed += 1
        cases.append({
            "id": item.get("id", query),
            "ok": bool(ok),
            "mode": mode,
            "query": query,
            "topic": topic,
            "events": len(result.get("events", [])),
            "warnings": result.get("warnings", []),
        })
    total = len(cases)
    return {
        "ok": passed == total,
        "passed": passed,
        "total": total,
        "metrics": {
            "case_pass_rate": passed / total if total else 1.0,
            "source_ref_coverage": 1.0 if not cases else sum(1 for c in cases if c["ok"]) / total,
        },
        "cases": cases,
    }
