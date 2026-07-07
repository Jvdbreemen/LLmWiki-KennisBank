#!/usr/bin/env python3
"""SessionEnd hook: sluit de retrieval-feedbackloop.

Leest welke documenten kb-retrieve deze sessie injecteerde (pending in
kb-usage.db) en scant het sessie-transcript op daadwerkelijk GEBRUIK:
een stem die voorkomt in assistant-tekst of in tool-call-input (bv. een
Read van dat artikel, of een [[stem]]-verwijzing in het antwoord) telt
als gebruikt. Bewust NIET de user/hook-berichten scannen: de injectie
zelf bevat de stems per definitie en zou elke injectie als "gebruikt"
aanmerken.

Het resultaat (used-counters + last_used) voedt de ranking-boost
(_rank.usage_factor) en de gebruiks-bewuste staleness (stale-check.py).

FAIL-OPEN, ALWAYS: elke fout -> stil exit 0. Telemetrie mag het einde van
een sessie nooit blokkeren. Gegate op de usage_telemetry-toggle.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def assistant_text(transcript_path: Path, cap_bytes: int = 20_000_000) -> str:
    """Alle assistant-tekst uit een JSONL-transcript.

    Fail-soft: onleesbare regels worden overgeslagen; een te groot bestand
    wordt afgekapt (telemetrie hoeft niet perfect te zijn).
    """
    chunks = []
    read = 0
    try:
        with transcript_path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                read += len(line)
                if read > cap_bytes:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content")
                if isinstance(content, str):
                    chunks.append(content)
                    continue
                for block in content or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        chunks.append(str(block.get("text", "")))
    except OSError:
        return ""
    return "\n".join(chunks)


def tool_use_input_text(transcript_path: Path, cap_bytes: int = 20_000_000) -> str:
    """Alle tool-call-inputs uit een JSONL-transcript."""
    chunks = []
    read = 0
    try:
        with transcript_path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                read += len(line)
                if read > cap_bytes:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content")
                if isinstance(content, str):
                    continue
                for block in content or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    try:
                        chunks.append(json.dumps(block.get("input", {}),
                                                 ensure_ascii=False))
                    except Exception:
                        continue
    except OSError:
        return ""
    return "\n".join(chunks)


def scan(session_id: str, transcript_path: Path) -> int:
    """Markeer pending stems als gebruikt op basis van het transcript.

    Returns het aantal als gebruikt gemarkeerde stems.
    """
    import _usage
    if not _usage.enabled():
        return 0
    pending = _usage.pending_for(session_id)
    if not pending:
        return 0
    text = tool_use_input_text(transcript_path) if transcript_path.exists() else ""
    used = [stem for stem in pending if stem and stem in text]
    n = _usage.mark_used(used) if used else 0
    _usage.clear_pending(session_id)
    return n


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except Exception:
        return 0
    session_id = str(data.get("session_id") or "")
    transcript = Path(str(data.get("transcript_path") or ""))
    if not session_id:
        return 0
    try:
        scan(session_id, transcript)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
