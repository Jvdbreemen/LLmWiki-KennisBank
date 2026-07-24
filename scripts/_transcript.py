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
    """Gestript transcript als tekst met '### USER'/'### ASSISTANT'-koppen."""
    chunks = [f"### {role.upper()}\n{text}" for role, text in iter_turns(jsonl_path)]
    return "\n\n".join(chunks) + ("\n" if chunks else "")
