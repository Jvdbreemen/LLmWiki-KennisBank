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
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vaultpath import vault_root  # noqa: E402

WATERMARK = ".swept"

#: De single-flight lock van de sweep. Woont hier en niet in sweep-launch.py,
#: omdat zowel de launcher (die hem neemt) als de sweep zelf (die hem als lease
#: ververst) hem nodig heeft.
LOCK_NAME = ".sweep.lock"

#: Hoe vaak refresh_lock() de mtime hoogstens aanraakt. De sweep roept hem aan
#: op elke transcript- en passgrens; zonder rem is dat een schrijfactie per
#: chunk voor een lease die in uren meet.
LOCK_REFRESH_SEC = 30

_last_refresh = 0.0


def lock_path(vault=None) -> Path:
    return (vault or vault_root()) / ".claude" / LOCK_NAME


def refresh_lock(vault=None, now=None) -> bool:
    """Vernieuw de lease op de sweep-lock. True als de mtime is aangeraakt.

    De lock werd door de launcher genomen en daarna door niemand meer
    aangeraakt, terwijl de staleness-check in uren rekent. "Ouder dan een uur"
    betekende daardoor "de sweep draait langer dan een uur", niet "de sweep is
    dood". Op een gegroeide vault haalt een sweep die drempel: gemeten liep een
    enkele onderhoudspass 23m52s over 4077 memories. De volgende launcher
    verklaarde de lock dan stale en spawnde een TWEEDE sweep naast de eerste.

    Dat is zelfversterkend. Twee sweeps delen dezelfde GPU, dus allebei worden
    ze trager, waardoor de drempel nog zekerder wordt overschreden. Waargenomen:
    drie gelijktijdige sweeps. Ze beschadigen elkaars data niet -- de watermark
    en de dedup dekken dat af, en een integriteitscheck op beide sqlite-bestanden
    kwam schoon terug -- maar ze verdrievoudigen wel het werk.

    Met een lease die tijdens het werk wordt ververst betekent een verlopen lock
    weer wat de naam belooft: er is niemand meer die eraan werkt.
    """
    global _last_refresh
    t = time.time() if now is None else now
    if t - _last_refresh < LOCK_REFRESH_SEC:
        return False
    p = lock_path(vault)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
    except OSError:
        # Fail-open: onderhoud mag nooit stoppen omdat een lease-touch faalt.
        return False
    _last_refresh = t
    return True


def release_lock(vault=None) -> None:
    """Geef de lock vrij. Fail-open: een niet-verwijderbare lock verloopt vanzelf."""
    try:
        lock_path(vault).unlink()
    except OSError:
        pass


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

#: Roles that count as conversation. "developer" is deliberately NOT one: that is
#: the injected instruction block (AGENTS.md, and inside it KennisBank's own
#: block), so capturing it would have the extractor summarise its own
#: instructions.
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
    """Reduce a transcript jsonl to flat user/assistant text. Fail-soft.

    Three shapes, because the vault archives transcripts from several clients:

    - Claude Code: every record has ``message`` with ``role`` and ``content``.
    - Codex: every record is ``{timestamp, type, payload}``. The conversation
      lives under ``type == "response_item"`` with ``payload.type == "message"``;
      the rest (``reasoning``, ``custom_tool_call``, ``function_call``,
      ``token_count``) is tool noise, exactly as the Claude branch already takes
      user/assistant only. ``event_msg``/``agent_message`` repeats the assistant
      text and is skipped so it cannot double-count.
    - Copilot: a hook event log of flat records where ``message`` is a STRING and
      ``role`` sits beside it. Only ``role == "user"`` carries conversation;
      ``tool_use`` and ``session`` are tooling and lifecycle. Assistant replies
      are absent from this format altogether, so it yields half a conversation --
      better than nothing, but not a full transcript.

    Without the Codex and Copilot branches this function returned NOTHING for 39
    of the 299 archived transcripts, together 94 MB of session content: a capture
    layer that was entirely blind rather than partly (TASK-145).
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
                    # The hook writes "userPromptSubmitted: <prompt>"; the event
                    # name is metadata and does not belong in the knowledge.
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
