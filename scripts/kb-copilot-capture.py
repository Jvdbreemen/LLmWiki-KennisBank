#!/usr/bin/env python3
"""KennisBank capture hook for the GitHub Copilot CLI (TASK-26.6).

Legacy event-capture helper retained for importing older Copilot hook data. It
is no longer registered by setup because the hookless Copilot integration uses
explicit command skills. The helper supports the former
Copilot lifecycle events (sessionStart, userPromptSubmitted, preToolUse,
postToolUse, sessionEnd). Copilot delivers a single-line JSON payload on stdin;
this script parses it, redacts known secret fields, and appends one structured
event line to a local staging log that TASK-26.8 imports into 01-raw/transcripts
and the temporal activity index.

Contract (ADR D3): **fail-open, always exit 0**. A missing vault, unparseable
payload, or any error must never block Copilot. In particular a preToolUse hook
that exits non-zero (code 2) would DENY the tool call; we never do that. We also
print nothing on stdout, so Copilot records no decision (= allow).

Privacy (AC#3): tool arguments and prompts are redacted for known secret keys
(token/secret/password/api_key/authorization/bearer/...) before they touch disk,
and every value is length-capped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCHEMA = "kb-copilot-event/1"
AGENT = "github-copilot-cli"
SOURCE = "copilot-hooks"
MAX_VALUE = 600

_SECRET_KEY_RE = re.compile(
    r"(?i)(token|secret|passwd|password|api[_-]?key|apikey|authorization|"
    r"bearer|credential|access[_-]?key|private[_-]?key|client[_-]?secret|"
    r"\bpat\b|session[_-]?token)"
)
# Inline secrets in freeform text (bearer tokens, KEY=VALUE with a secret name).
_INLINE_SECRET_RE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._\-]+"
    r"|(?:token|secret|password|api[_-]?key|authorization)\s*[=:]\s*\S+"
    r"|gh[posru]_[A-Za-z0-9]{16,}"
    r"|sk-[A-Za-z0-9]{16,})"
)
REDACTED = "***"


def _vault() -> Path:
    raw = os.environ.get("KENNISBANK_VAULT") or str(Path(__file__).resolve().parents[2])
    return Path(raw)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _to_iso(value) -> str:
    """Copilot timestamps: camelCase events give Unix ms (number); PascalCase
    give ISO strings. Normalize to ISO; fall back to now on anything odd."""
    if isinstance(value, (int, float)) and value > 0:
        try:
            secs = value / 1000.0 if value > 10_000_000_000 else float(value)
            return datetime.fromtimestamp(secs, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        except (ValueError, OSError, OverflowError):
            return _now_iso()
    s = str(value or "").strip()
    if not s:
        return _now_iso()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return _now_iso()


def redact_text(text: str) -> str:
    text = _INLINE_SECRET_RE.sub(REDACTED, str(text or ""))
    return text[:MAX_VALUE]


def redact_value(key: str, value):
    if _SECRET_KEY_RE.search(str(key)):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value("", v) for v in value[:20]]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_args(raw) -> str:
    """toolArgs arrives as a JSON string. Redact by key when parseable, else
    scrub the freeform string. Always length-capped."""
    if raw is None:
        return ""
    if isinstance(raw, (dict, list)):
        obj = raw
    else:
        s = str(raw)
        try:
            obj = json.loads(s)
        except (ValueError, TypeError):
            return redact_text(s)
    red = redact_value("", obj)
    try:
        return json.dumps(red, ensure_ascii=False)[:MAX_VALUE]
    except (TypeError, ValueError):
        return redact_text(str(red))


def _get(payload: dict, *keys):
    for k in keys:
        if k in payload and payload[k] not in (None, ""):
            return payload[k]
    return ""


def build_event(event_name: str, payload: dict) -> dict:
    sid = str(_get(payload, "sessionId", "session_id") or "unknown")
    cwd = str(_get(payload, "cwd", "workingDirectory"))
    ts = _to_iso(_get(payload, "timestamp", "time"))
    tool = str(_get(payload, "toolName", "tool_name", "tool"))
    args_red = redact_args(_get(payload, "toolArgs", "tool_args", "arguments"))
    prompt = str(_get(payload, "initialPrompt", "prompt", "userPrompt"))
    source_kind = str(_get(payload, "source"))

    if tool:
        message = f"{event_name} {tool}: {args_red}".strip()
        role = "tool_use"
    elif prompt:
        message = f"{event_name}: {redact_text(prompt)}"
        role = "user"
    else:
        message = event_name + (f" ({source_kind})" if source_kind else "")
        role = "session"

    return {
        "schema": SCHEMA,
        "source": SOURCE,
        "agent": AGENT,
        "event": event_name,
        "session_id": sid,
        "cwd": cwd,
        "timestamp": ts,
        "tool": tool,
        "role": role,
        "message": message[:MAX_VALUE * 2],
    }


def _safe_name(sid: str) -> str:
    # Session ids are UUIDs; drop dots too so no ".."/traversal-looking name can
    # form, and collapse the resulting separators.
    name = re.sub(r"[^A-Za-z0-9_-]", "-", sid or "unknown")
    name = re.sub(r"-+", "-", name).strip("-") or "unknown"
    return name[:80]


def output_path(vault: Path, session_id: str) -> Path:
    return vault / ".claude" / "copilot-events" / f"{_safe_name(session_id)}.jsonl"


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_stdin() -> dict:
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        # Copilot promises single-line JSON; tolerate a stray trailing line.
        try:
            data = json.loads(raw.splitlines()[0])
        except (ValueError, TypeError, IndexError):
            return {}
    return data if isinstance(data, dict) else {}


def _capture_disabled() -> bool:
    """Honor the wrapper's --no-capture (KENNISBANK_COPILOT_NO_CAPTURE=1)."""
    return str(os.environ.get("KENNISBANK_COPILOT_NO_CAPTURE", "")).strip().lower() in ("1", "true", "yes", "on")


def run(event_name: str, payload: dict, *, vault: "Path | None" = None,
        out: "Path | None" = None) -> "Path | None":
    """Capture one event. Returns the written path (or None if skipped). Never
    raises: the caller must stay fail-open."""
    try:
        if _capture_disabled():
            return None
        vault = vault or _vault()
        event = build_event(event_name or "unknown", payload or {})
        path = out or output_path(vault, event["session_id"])
        append_event(path, event)
        return path
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default=os.environ.get("COPILOT_HOOK_EVENT", "unknown"))
    ap.add_argument("--vault")
    ap.add_argument("--out")
    ap.add_argument("--print-path", action="store_true",
                    help="print the written path to stderr (diagnostics only)")
    try:
        args = ap.parse_args(argv)
        payload = _read_stdin()
        vault = Path(args.vault) if args.vault else None
        out = Path(args.out) if args.out else None
        path = run(args.event, payload, vault=vault, out=out)
        if args.print_path and path:
            print(str(path), file=sys.stderr)
    except Exception:
        # Fail-open: swallow everything. Never emit a non-zero exit that could
        # deny a Copilot tool call.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
