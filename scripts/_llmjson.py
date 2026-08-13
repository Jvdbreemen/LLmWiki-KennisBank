#!/usr/bin/env python3
"""_llmjson.py - pull JSON out of a model answer that is not only JSON.

Every seam did this the same way: `raw[raw.find("{"):raw.rfind("}") + 1]`.
That is the WIDEST possible span, and therefore exactly the wrong one. A model
that keeps talking after its JSON --

    {"action": "ADD", "reason": "new"}
    I chose this because {…} did not apply here.

-- yields a span running to the last brace in the COMMENTARY, and the parse
fails. Every seam is fail-safe, so that failure is silent: extract returns [],
reconcile returns ADD, the judge returns unverified. Measured in the TASK-142
sweep: qwen3.5:9b did this twice in twenty calls; the 4b not once in fifty-four.

The fix is not wider but narrower: take the FIRST complete object or array, by
counting brackets with awareness of strings and escapes. What comes after is
the model's commentary, not data.

Stdlib. No side effects on import.
"""
from __future__ import annotations

import json

_PAREN = {"{": "}", "[": "]"}


def _span_from(raw: str, open_ch: str, start_at: int) -> "tuple[int, int] | None":
    """(start, end) of the first complete bracket pair from position `start_at`.

    Counts depth and skips everything inside a string, because a brace in a
    reason text ("do not use {var}") must not count -- that is precisely what
    makes the wide span so unreliable.
    """
    close_ch = _PAREN[open_ch]
    start = raw.find(open_ch, start_at)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(raw)):
        c = raw[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return start, i
    return None


#: How many opening brackets to try at most. A model that has not produced
#: valid JSON after twenty candidates is not going to; the bound keeps a
#: pathological answer cheap.
_MAX_CANDIDATES = 20


def _parse(raw, open_ch: str, expected):
    text = str(raw or "")
    # Try EVERY opening bracket, not just the first. A model that opens with
    # "Let me {think} about it. {\"action\": \"ADD\"}" puts a brace BEFORE the
    # JSON; trying only the first picks `{think}`, fails, and falls back to the
    # wide span which also fails -- exactly the silent parse error this module
    # exists to remove.
    start_at = 0
    for _ in range(_MAX_CANDIDATES):
        span = _span_from(text, open_ch, start_at)
        if not span:
            break
        try:
            value = json.loads(text[span[0]:span[1] + 1])
            if isinstance(value, expected):
                return value
        except Exception:
            pass
        start_at = span[0] + 1
    # Fall back to the old, wider span. It is weaker, but it can resolve a
    # case the counter misses (an unterminated string somewhere at the end,
    # say) and can never break a case the counter already resolved.
    s, e = text.find(open_ch), text.rfind(_PAREN[open_ch])
    if s >= 0 and e > s:
        try:
            value = json.loads(text[s:e + 1])
            if isinstance(value, expected):
                return value
        except Exception:
            pass
    return None


def first_object(raw) -> "dict | None":
    """The first complete JSON object in the text, or None."""
    return _parse(raw, "{", dict)


def first_array(raw) -> "list | None":
    """The first complete JSON array in the text, or None."""
    return _parse(raw, "[", list)
