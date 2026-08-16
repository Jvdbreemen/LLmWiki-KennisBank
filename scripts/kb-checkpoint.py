#!/usr/bin/env python3
"""kb-checkpoint.py — checkpoint-primitief (TASK-79, idee uit Mind).

Twee soorten checkpoints, één state-bestand:

* AUTO (PreCompact-hook, Claude-only): vlak vóór context-compaction schrijft
  deze hook een mechanische stub (transcript-pad, sessie, tijdstip) naar de
  state. Side-effect only — PreCompact kan geen context injecteren. Gate:
  toggle ``checkpoints`` (default UIT, opt-in).
* MANUAL (--register, aangeroepen door /checkpoint in elke client): registreert
  een agent-geschreven checkpoint-markdown uit 01-raw/checkpoints/ als pending.
  Draait ALTIJD, ongeacht de toggle — wie /checkpoint typt, wil een checkpoint
  (zelfde principe als distill-notify's subcommando's).

Het herstel-pad (--notify) draait bij SessionStart vóór de freshness-gate en
meldt pending checkpoints als additionalContext. --done sluit pending
checkpoints af (aangeroepen door /checkpoint done en door /sessielog).

FAIL-OPEN, ALTIJD: elke fout eindigt met exit 0. Stdlib-only (ADR-0002).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

STATE_NAME = "kb-checkpoint-state.json"
CHECKPOINT_DIR = ("01-raw", "checkpoints")
# Een auto-stub jonger dan dit is vermoedelijk van de compaction die NU bezig
# is; de melding daarover komt zo meteen vanzelf via SessionStart(compact).
MAX_PENDING = 20


def state_path(vault: Path) -> Path:
    return vault / ".claude" / STATE_NAME


def _load(vault: Path) -> dict:
    try:
        data = json.loads(state_path(vault).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(vault: Path, data: dict) -> None:
    p = state_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".kbckpt-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def pending(vault: Path) -> list[dict]:
    entries = _load(vault).get("pending")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _append(vault: Path, entry: dict) -> None:
    data = _load(vault)
    items = data.get("pending")
    items = [e for e in items if isinstance(e, dict)] if isinstance(items, list) else []
    items.append(entry)
    # Begrensd: een hook die in een loop raakt mag de state niet onbegrensd
    # laten groeien. Oudste eruit, nieuwste blijft.
    data["pending"] = items[-MAX_PENDING:]
    _save(vault, data)


def record_precompact(vault: Path, payload: dict) -> bool:
    """PreCompact: schrijf een auto-stub. Gate op de checkpoints-toggle."""
    try:
        import _settings
        if not _settings.get("checkpoints", False):
            return False
    except Exception:
        return False  # toggle onleesbaar -> opt-in default: niets doen
    _append(vault, {
        "type": "auto",
        "created_at": time.time(),
        "trigger": str(payload.get("trigger") or ""),
        "session_id": str(payload.get("session_id") or ""),
        "transcript_path": str(payload.get("transcript_path") or ""),
        "cwd": str(payload.get("cwd") or ""),
    })
    return True


def register_manual(vault: Path, md_path: str) -> str | None:
    """Registreer een agent-geschreven checkpoint-markdown. Pad moet onder
    01-raw/checkpoints/ liggen (zelfde strengheid als kb-session-log.py)."""
    target = Path(md_path).resolve()
    allowed = (vault / CHECKPOINT_DIR[0] / CHECKPOINT_DIR[1]).resolve()
    try:
        target.relative_to(allowed)
    except ValueError:
        return f"geweigerd: {md_path} ligt niet onder {allowed}"
    if not target.is_file():
        return f"geweigerd: {md_path} bestaat niet"
    _append(vault, {
        "type": "manual",
        "created_at": time.time(),
        "path": str(target),
    })
    return None


def mark_done(vault: Path) -> int:
    """Sluit alle pending checkpoints af. Idempotent; return aantal gesloten."""
    data = _load(vault)
    items = data.get("pending")
    count = len([e for e in items if isinstance(e, dict)]) if isinstance(items, list) else 0
    if count == 0:
        return 0
    done = data.get("done")
    done = done if isinstance(done, list) else []
    stamp = time.time()
    for e in items:
        if isinstance(e, dict):
            e["done_at"] = stamp
            done.append(e)
    data["pending"] = []
    data["done"] = done[-MAX_PENDING:]
    _save(vault, data)
    return count


def _describe(entry: dict) -> str:
    stamp = entry.get("created_at")
    when = ""
    if isinstance(stamp, (int, float)):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp))
    if entry.get("type") == "manual":
        return f"handmatig checkpoint van {when}: {entry.get('path', '?')}"
    return (f"auto-checkpoint van {when} (compaction, "
            f"transcript: {entry.get('transcript_path') or 'onbekend'})")


def notify_text(vault: Path, source: str) -> str:
    items = pending(vault)
    if not items:
        return ""
    lead = ("Context-compaction net gebeurd; er staat een werkstand-checkpoint klaar."
            if source == "compact" else
            f"{len(items)} open checkpoint(s) van een eerdere sessie gevonden.")
    lines = [lead]
    lines.extend(f"- {_describe(e)}" for e in items[-3:])
    lines.append("Draai /checkpoint load om de werkstand te herstellen, "
                 "of /checkpoint done om ze af te sluiten.")
    return "\n".join(lines)


def _emit(text: str) -> None:
    if not text:
        return
    sys.stdout.write(json.dumps({
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"KennisBank checkpoint: {text}",
        },
    }))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        raw = b""
        if not sys.stdin.isatty():
            try:
                raw = sys.stdin.buffer.read()
            except OSError:
                raw = b""
        vault = vault_root()

        if argv and argv[0] == "--notify":
            source = ""
            if "--source" in argv:
                i = argv.index("--source")
                source = argv[i + 1] if i + 1 < len(argv) else ""
            _emit(notify_text(vault, source))
            return 0
        if argv and argv[0] == "--register":
            if len(argv) < 2:
                print("usage: kb-checkpoint.py --register <pad-onder-01-raw/checkpoints>",
                      file=sys.stderr)
                return 0
            err = register_manual(vault, argv[1])
            print(f"[kb-checkpoint] {err}" if err else "[kb-checkpoint] geregistreerd",
                  file=sys.stderr)
            return 0
        if argv and argv[0] == "--list":
            for e in pending(vault):
                print(_describe(e))
            return 0
        if argv and argv[0] == "--done":
            n = mark_done(vault)
            print(f"[kb-checkpoint] afgesloten: {n} checkpoint(s)", file=sys.stderr)
            return 0

        # Geen subcommando: PreCompact-hookmodus.
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace")) if raw.strip() else {}
        except ValueError:
            payload = {}
        record_precompact(vault, payload if isinstance(payload, dict) else {})
    except Exception as exc:  # noqa: BLE001 — fail-open, sessie mag hier nooit op stuklopen
        print(f"[kb-checkpoint] unexpected: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
