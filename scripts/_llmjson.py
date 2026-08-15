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

A SECOND failure shape, found while validating the grounded verifier: the model
emits an object whose STRUCTURE is right and whose string delimiters are wrong.
Two variants, both from qwen3.5:4b, four times in fifty-six calls:

    {"verdict": "supported", "reason": \"the passage states …\"}
    {"verdict": "unsupported", "reason": 'the passage describes …'}

No span-finding fixes those, because there is nothing wrong with the span. They
are repaired here instead -- but only after an honest parse has already failed,
and only if the repaired text then parses. A repair that does not yield valid
JSON is discarded, so a broken answer stays broken rather than becoming a
plausible wrong one.

Stdlib. No side effects on import.
"""
from __future__ import annotations

import json
import re

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


#: A string value the model delimited with single quotes instead of double.
#: Anchored on the colon so it can only ever touch a VALUE: a key in single
#: quotes stays broken, because rewriting one was never observed and guessing
#: is how a repair pass starts inventing data. The lookahead keeps the closing
#: delimiter unconsumed so two such values in a row both match.
_SINGLE_QUOTED_VALUE = re.compile(
    r"(:\s*)'((?:[^'\\]|\\.)*)'(?=\s*(?:[,}\]\n]|$))")


def _single_to_double(text: str) -> str:
    def swap(m):
        inner = m.group(2).replace('\\"', '"').replace('"', '\\"')
        return f'{m.group(1)}"{inner}"'
    return _SINGLE_QUOTED_VALUE.sub(swap, text)


def _variants(text: str):
    """The text as written, then repairs, each tried only if the last failed.

    Order is not cosmetic: the unmodified text goes first, so an answer that
    parses today parses identically tomorrow and no repair can reinterpret it.
    """
    yield text
    seen = {text}
    for candidate in (text.replace('\\"', '"'),
                      _single_to_double(text),
                      _single_to_double(text.replace('\\"', '"'))):
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


def _scan(text: str, open_ch: str, expected):
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


def _parse(raw, open_ch: str, expected):
    for candidate in _variants(str(raw or "")):
        value = _scan(candidate, open_ch, expected)
        if value is not None:
            return value
    return None


def first_object(raw) -> "dict | None":
    """The first complete JSON object in the text, or None."""
    return _parse(raw, "{", dict)


def first_array(raw) -> "list | None":
    """The first complete JSON array in the text, or None."""
    return _parse(raw, "[", list)
