#!/usr/bin/env python3
"""_sweepstate.py - watermark + transcript-reader voor de capture-sweep.

Spiegelt distill-notify's .distilled-pattern met een EIGEN .swept-watermark, zodat
de geheugen-sweep onafhankelijk van de destillatie bijhoudt welke transcripts al
tot memory verwerkt zijn. transcript_text() reduceert een CC-.jsonl tot platte
user/assistant-tekst (fail-soft).

Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK = ".swept"


def _tdir(vault=None) -> Path:
    return (vault or vault_root()) / "01-raw" / "transcripts"


def _watermark(vault=None) -> set:
    f = _tdir(vault) / WATERMARK
    try:
        return {ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except OSError:
        return set()


def pending(vault=None) -> list:
    d = _tdir(vault)
    if not d.exists():
        return []
    done = _watermark(vault)
    return [p for p in sorted(d.glob("*.jsonl")) if p.stem not in done]


def mark(stems, vault=None) -> int:
    done = _watermark(vault)
    new = [s for s in dict.fromkeys(stems) if s and s not in done]
    if not new:
        return 0
    f = _tdir(vault) / WATERMARK
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            for s in new:
                fh.write(s + "\n")
    except OSError as e:
        print(f"[sweepstate] kan watermark niet schrijven: {e}", file=sys.stderr)
        return 0
    return len(new)


#: Content-block kinds that carry conversation text. Claude Code writes "text";
#: Codex writes "input_text" on the way in and "output_text" on the way out.
_TEXT_BLOCKS = ("text", "input_text", "output_text")

#: Rollen die als gesprek tellen. "developer" hoort er NIET bij: dat is het
#: ingespoten instructieblok (AGENTS.md, en daarin het KennisBank-blok zelf),
#: dus meenemen zou de extractor zijn eigen instructies laten samenvatten.
_ROLES = ("user", "assistant")


def _block_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in _TEXT_BLOCKS:
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def transcript_text(jsonl_path) -> str:
    """Reduceer een transcript-jsonl tot platte user/assistant-tekst. Fail-soft.

    Twee formaten, omdat de vault transcripts van meerdere clients archiveert:

    - Claude Code: elk record heeft ``message`` met ``role`` en ``content``.
    - Codex: elk record is ``{timestamp, type, payload}``. Het gesprek zit in
      ``type == "response_item"`` met ``payload.type == "message"``; de rest
      (``reasoning``, ``custom_tool_call``, ``function_call``, ``token_count``)
      is gereedschapsruis, net zoals de Claude-tak alleen user/assistant pakt.
      ``event_msg``/``agent_message`` herhaalt de assistent-tekst en wordt
      overgeslagen om dubbeltelling te voorkomen.
    - Copilot: een hook-eventlog met platte records waarin ``message`` een
      STRING is en ``role`` naast ``message`` staat. Alleen ``role == "user"``
      draagt gesprek; ``tool_use`` en ``session`` zijn gereedschap en
      levenscyclus. Assistent-antwoorden staan er niet in -- dit formaat levert
      dus de helft van een gesprek, en dat is beter dan niets maar het is geen
      volwaardig transcript.

    Zonder de Codex- en Copilot-takken leverde deze functie NIETS terug voor 39
    van de 299 gearchiveerde transcripts, samen 94 MB sessie-inhoud: een compleet
    onzichtbare capture-laag in plaats van een gedeeltelijke (TASK-145).
    """
    out = []
    try:
        with Path(jsonl_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message")
                if isinstance(msg, dict):
                    role = msg.get("role")
                    if role in _ROLES:
                        t = _block_text(msg.get("content")).strip()
                        if t:
                            out.append(f"{role}: {t}")
                    continue
                if isinstance(msg, str) and rec.get("role") in _ROLES:
                    role = rec.get("role")
                    t = msg.strip()
                    # De hook schrijft "userPromptSubmitted: <prompt>"; de
                    # eventnaam is metadata en hoort niet in de kennis.
                    event = str(rec.get("event") or "")
                    if event and t.startswith(event + ":"):
                        t = t[len(event) + 1:].strip()
                    if t:
                        out.append(f"{role}: {t}")
                    continue
                payload = rec.get("payload")
                if rec.get("type") == "response_item" and isinstance(payload, dict) \
                        and payload.get("type") == "message":
                    role = payload.get("role")
                    if role in _ROLES:
                        t = _block_text(payload.get("content")).strip()
                        if t:
                            out.append(f"{role}: {t}")
    except Exception:
        return ""
    return "\n\n".join(out)
