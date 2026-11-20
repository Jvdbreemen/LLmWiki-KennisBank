#!/usr/bin/env python3
"""_transcript.py - mechanische helpers voor Claude Code transcript-.jsonl.

Deelt de content->tekst-reductie tussen import-cc-history.py (stub-"Doel") en
strip-transcript.py (volledige gestripte conversatie voor destillatie). Geen
LLM en geen I/O buiten het lezen van een enkele .jsonl. Zie _extract.py voor de
LLM-kandidaat-extractie; dat is een andere verantwoordelijkheid.

Transcript-formaat: een jsonl met een record per regel. Conversatie-turns hebben
`type` user|assistant en een `message: {role, content}`. `content` is een string
of een lijst blocks met `type` text|thinking|tool_use|tool_result|image.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def extract_text(content, include_tool_result: bool = True) -> str:
    """Reduceer message.content (string of list-of-blocks) tot platte tekst.

    include_tool_result=True (default) behoudt tool_result-tekst - het gedrag
    waar import-cc-history op leunt. False laat tool_result vallen; dat is wat de
    stripper wil, want tool-output is ruis voor destillatie. thinking, tool_use
    en image worden altijd genegeerd.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_result" and include_tool_result:
                tr = block.get("content", "")
                if isinstance(tr, str):
                    parts.append(tr)
                elif isinstance(tr, list):
                    for sub in tr:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            parts.append(sub.get("text", ""))
            # negeer thinking, tool_use, image (en tool_result als include False)
        return "\n".join(p for p in parts if p)
    return ""


def iter_turns(jsonl_path) -> Iterator[tuple[str, str]]:
    """Yield (role, text) voor elke echte conversatie-turn in een .jsonl.

    Alleen user/assistant-turns die geen isSidechain zijn en na strippen niet-
    leeg zijn. Een tool_result-only user-turn levert geen tekst en valt dus weg.
    Fail-safe: onleesbare of kapotte regels worden overgeslagen, geen exceptie.
    """
    path = Path(jsonl_path)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant"):
                continue
            if rec.get("isSidechain"):
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            text = extract_text(msg.get("content"), include_tool_result=False).strip()
            if text:
                yield role, text


def strip_to_text(jsonl_path) -> str:
    """Gestript transcript als tekst met '### USER'/'### ASSISTANT'-koppen.

    Codex and Copilot transcripts have no Claude Code ``message`` records, so
    iter_turns() yields nothing for them. Without a fallback 18 archived Codex
    sessions stripped to 0 characters and /destilleer read them as "nothing to
    learn" (2026-11-20, the same blind spot TASK-145 fixed in the sweep). Fall
    back to the sweep's three-format reader, which keeps user/assistant only.

    The fallback runs ONLY for a file without Claude Code records. A Claude
    transcript that strips to nothing (sidechain-only, say) stays empty: the
    sweep reader has no sidechain filter and would bring subagent text back.
    """
    chunks = [f"### {role.upper()}\n{text}" for role, text in iter_turns(jsonl_path)]
    if not chunks and not _has_claude_records(jsonl_path):
        from _sweepstate import transcript_text  # lazy: only for non-Claude formats
        text = transcript_text(jsonl_path)
        return text + "\n" if text else ""
    return "\n\n".join(chunks) + ("\n" if chunks else "")


def _has_claude_records(jsonl_path) -> bool:
    """True as soon as one record has a Claude Code ``message`` object."""
    try:
        with Path(jsonl_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict) and isinstance(rec.get("message"), dict):
                    return True
    except OSError:
        return False
    return False


def is_agent_invocation(src) -> bool:
    """True when a transcript is a one-shot plugin/agent LLM call, not a session.

    The runtime gives such calls their own session id, so SessionEnd archives
    them and the importer turns them into session stubs. Shared by
    archive-transcript.py and import-cc-history.py so the two cannot drift: the
    importer kept the old first-line rule after the archiver was fixed.

    Signal: the user records carry ``entrypoint == "sdk-cli"`` AND there is at
    most one real prompt turn (tool_result-only user records do not count).
    The earlier signal, "the first line is a queue-operation", broke both ways
    once the runtime started writing a ``session-owner`` record first: 885 of
    1213 archived transcripts on 2026-11-20 were one-shot SDK calls (adr-kit
    judge, KennisBank's own reconcile prompts, probes) that it let through,
    while a real ``cli`` session that starts with a queued prompt (10 prompts,
    first record queue-operation) was dropped while that line still came first.
    Over the same archive the new rule matched 885 files, all automated, and no
    interactive session.

    Fail-open: any doubt or read error answers False, so a real session is
    never lost.
    """
    try:
        entrypoint, prompts = None, 0
        with Path(src).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"user"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    # A damaged record may be a later prompt; never let it turn a
                    # multi-turn session into a "one-shot" that gets skipped.
                    return False
                if not isinstance(rec, dict) or rec.get("type") != "user" \
                        or rec.get("isSidechain"):
                    continue
                entrypoint = entrypoint or rec.get("entrypoint")
                if entrypoint != "sdk-cli":
                    return False
                content = (rec.get("message") or {}).get("content")
                if isinstance(content, list) and content and all(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content):
                    continue
                prompts += 1
                if prompts > 1:
                    return False
        return entrypoint == "sdk-cli" and prompts == 1
    except Exception:
        return False
