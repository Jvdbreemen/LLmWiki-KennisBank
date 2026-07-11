#!/usr/bin/env python3
"""Import GitHub Copilot CLI activity into KennisBank rawlogs (TASK-26.8).

Two sources, both local, both stamped `agent=github-copilot-cli`:

- **copilot-hooks** (default, verified): the JSONL events the capture hook
  (kb-copilot-capture.py) writes to `<vault>/.claude/copilot-events/*.jsonl`.
- **copilot-history** (opt-in, best-effort): Copilot's own session-state JSONL
  under the Copilot config home. The exact schema is not contractually stable,
  so this path is defensive and off by default (`--include-history`).

Normalized events are written to `<vault>/01-raw/transcripts/copilot-<sid>.jsonl`
in the generic transcript shape the temporal activity index already reads
(`iter_transcript_events`), so recall via /watdeedik, /timeline and topic
timeline picks them up on the next `build-activity-index` run.

Idempotent: events are deduped by a stable id (session_id + timestamp + event +
message). Active/incomplete logs are skipped unless `--include-active`: a staging
file modified within `--active-window` seconds is assumed to be the live session
and left for the next run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AGENT = "github-copilot-cli"
_INLINE_SECRET_RE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._\-]+"
    r"|(?:token|secret|password|api[_-]?key|authorization)\s*[=:]\s*\S+"
    r"|gh[posru]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,})"
)


def _vault(arg: str | None) -> Path:
    raw = arg or os.environ.get("KENNISBANK_VAULT") or str(Path(__file__).resolve().parents[2])
    return Path(raw)


def _copilot_home() -> Path:
    raw = os.environ.get("COPILOT_HOME", "").strip()
    if raw:
        return Path(raw)
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(home) / ".copilot"


def _redact(text: str) -> str:
    return _INLINE_SECRET_RE.sub("***", str(text or ""))[:1200]


def _event_id(ev: dict) -> str:
    blob = "\x1f".join(str(ev.get(k, "")) for k in ("session_id", "timestamp", "event", "message"))
    return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:24]


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _normalize_hook_event(ev: dict) -> dict:
    """Hook events are already normalized + redacted by the capture script."""
    sid = str(ev.get("session_id") or "unknown")
    return {
        "id": _event_id(ev),
        "agent": AGENT,
        "source": ev.get("source") or "copilot-hooks",
        "session_id": sid,
        "event": ev.get("event") or "",
        "timestamp": ev.get("timestamp") or "",
        "cwd": ev.get("cwd") or "",
        "tool": ev.get("tool") or "",
        "role": ev.get("role") or "session",
        "message": ev.get("message") or "",
    }


def _normalize_history_event(ev: dict, sid: str) -> dict | None:
    """Best-effort normalization of a Copilot session-state line (opt-in).

    Defensive: extract only recognizable fields; redact freeform text; skip
    anything without a usable message so an unknown schema cannot corrupt the
    rawlog."""
    ts = ev.get("timestamp") or ev.get("time") or ev.get("created_at") or ""
    msg = ev.get("message") or ev.get("text") or ev.get("content") or ev.get("prompt") or ""
    if isinstance(msg, (dict, list)):
        msg = json.dumps(msg, ensure_ascii=False)
    msg = _redact(str(msg))
    if not msg.strip():
        return None
    role = str(ev.get("role") or ev.get("type") or "transcript")
    out = {
        "agent": AGENT, "source": "copilot-history", "session_id": sid,
        "event": role, "timestamp": str(ts), "cwd": str(ev.get("cwd") or ""),
        "tool": "", "role": role, "message": msg,
    }
    out["id"] = _event_id(out)
    return out


def _write_transcript(vault: Path, sid: str, events: list[dict]) -> tuple[Path, int, int]:
    """Merge events into 01-raw/transcripts/copilot-<sid>.jsonl, deduped by id.
    Returns (path, new_count, duplicate_count)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", sid)
    safe = re.sub(r"-+", "-", safe).strip("-")[:80] or "unknown"
    path = vault / "01-raw" / "transcripts" / f"copilot-{safe}.jsonl"
    existing = {_event_id(e) if "id" not in e else e["id"]: e for e in _read_jsonl(path)}
    new = 0
    dup = 0
    for ev in events:
        eid = ev["id"]
        if eid in existing:
            dup += 1
        else:
            existing[eid] = ev
            new += 1
    if new:
        merged = sorted(existing.values(), key=lambda e: (str(e.get("timestamp") or ""), e.get("id", "")))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for ev in merged:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return path, new, dup


def import_hooks(vault: Path, *, active_window: float, include_active: bool,
                 events_dir: Path | None = None, now: float | None = None) -> dict:
    staging = events_dir or (vault / ".claude" / "copilot-events")
    result = {"source": "copilot-hooks", "sessions": 0, "events": 0,
              "duplicates": 0, "skipped_active": 0, "files": []}
    if not staging.is_dir():
        return result
    now = now if now is not None else time.time()
    for path in sorted(staging.glob("*.jsonl")):
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if not include_active and age < active_window:
            result["skipped_active"] += 1
            continue
        raw = _read_jsonl(path)
        if not raw:
            continue
        by_sid: dict[str, list[dict]] = {}
        for ev in raw:
            norm = _normalize_hook_event(ev)
            by_sid.setdefault(norm["session_id"], []).append(norm)
        for sid, evs in by_sid.items():
            _tp, new, dup = _write_transcript(vault, sid, evs)
            result["sessions"] += 1
            result["events"] += new
            result["duplicates"] += dup
        result["files"].append(path.name)
    return result


def import_history(vault: Path, *, home: Path | None = None) -> dict:
    home = home or _copilot_home()
    result = {"source": "copilot-history", "sessions": 0, "events": 0, "duplicates": 0}
    for sub in ("session-state", "history-session-state"):
        root = home / sub
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.jsonl")):
            sid = path.stem
            evs = []
            for ev in _read_jsonl(path):
                norm = _normalize_history_event(ev, sid)
                if norm:
                    evs.append(norm)
            if not evs:
                continue
            _tp, new, dup = _write_transcript(vault, sid, evs)
            result["sessions"] += 1
            result["events"] += new
            result["duplicates"] += dup
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import Copilot CLI activity into KennisBank rawlogs")
    ap.add_argument("--vault")
    ap.add_argument("--active-window", type=float, default=120.0,
                    help="seconds: staging files newer than this are treated as the live session and skipped")
    ap.add_argument("--include-active", action="store_true")
    ap.add_argument("--include-history", action="store_true",
                    help="also import Copilot's own session-state (best-effort, opt-in)")
    ap.add_argument("--events-dir", help="override the copilot-events staging dir (tests)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    vault = _vault(args.vault)
    events_dir = Path(args.events_dir) if args.events_dir else None
    report = {"vault": str(vault), "results": []}
    report["results"].append(import_hooks(
        vault, active_window=args.active_window, include_active=args.include_active,
        events_dir=events_dir))
    if args.include_history:
        report["results"].append(import_history(vault))
    report["events"] = sum(r["events"] for r in report["results"])
    report["sessions"] = sum(r["sessions"] for r in report["results"])

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for r in report["results"]:
            print(f"{r['source']}: {r['sessions']} sessions, {r['events']} events, "
                  f"{r['duplicates']} dup, {r.get('skipped_active', 0)} active-skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
