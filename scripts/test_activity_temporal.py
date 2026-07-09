#!/usr/bin/env python3
"""Temporal-parsing test set for the KennisBank activity recall.

Exercises _activity.parse_period against a fixed reference date so every
expected value is deterministic. Runnable standalone:

    python3 test_activity_temporal.py

Exits 0 when all cases pass, 1 otherwise. Also importable by pytest: each
CASES entry becomes an assertion via test_temporal_cases().

Reference "now" is Thursday 2026-07-09 12:00 local. Derived anchors:
  today=2026-07-09 (Thu, weekday 3)   this Monday=2026-07-06
  yesterday=07-08  day-before=07-07   last Monday=2026-06-29
"""
from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _activity  # noqa: E402

NOW = datetime.datetime(2026, 7, 9, 12, 0)

# Each case: query -> expectations.
#   start / end : ISO date (YYYY-MM-DD); end is the exclusive upper bound.
#   ok          : False means a parse error is expected.
#   topic       : expected extracted topic (when the phrase carries one).
# Only the provided keys are asserted, so a case may check just the start.
CASES: list[dict] = [
    # --- absolute single day ---
    {"q": "2026-07-03", "start": "2026-07-03", "end": "2026-07-04"},
    {"q": "3 juli 2026", "start": "2026-07-03", "end": "2026-07-04"},
    {"q": "July 3 2026", "start": "2026-07-03", "end": "2026-07-04"},

    # --- relative single day ---
    {"q": "vandaag", "start": "2026-07-09", "end": "2026-07-10"},
    {"q": "today", "start": "2026-07-09"},
    {"q": "gisteren", "start": "2026-07-08", "end": "2026-07-09"},
    {"q": "yesterday", "start": "2026-07-08"},
    {"q": "eergisteren", "start": "2026-07-07", "end": "2026-07-08"},
    {"q": "day before yesterday", "start": "2026-07-07", "end": "2026-07-08"},  # multi-word EN: must beat "yesterday" substring
    {"q": "this monday", "start": "2026-07-06"},                                # this week's Monday (already passed)
    {"q": "this friday", "start": "2026-07-10"},                               # this week's Friday (still upcoming)
    {"q": "deze vrijdag", "start": "2026-07-10"},                              # nl: this week's Friday
    {"q": "this saturday", "start": "2026-07-11"},                            # this week's Saturday (future)

    # --- relative weekday (bare + directional) ---
    {"q": "zaterdag", "start": "2026-07-04"},
    {"q": "afgelopen zaterdag", "start": "2026-07-04"},
    {"q": "afgelopen zondag", "start": "2026-07-05"},
    {"q": "afgelopen maandag", "start": "2026-07-06"},
    {"q": "afgelopen donderdag", "start": "2026-07-02"},   # today is Thu -> a week back
    {"q": "vorige vrijdag", "start": "2026-07-03"},
    {"q": "komende maandag", "start": "2026-07-13"},
    {"q": "volgende vrijdag", "start": "2026-07-10"},
    {"q": "last friday", "start": "2026-07-03"},

    # --- weekday within a relative week ---
    {"q": "vorige week maandag", "start": "2026-06-29", "end": "2026-06-30"},
    {"q": "deze week maandag", "start": "2026-07-06"},
    {"q": "deze week vrijdag", "start": "2026-07-10"},
    {"q": "komende week woensdag", "start": "2026-07-15"},

    # --- whole relative weeks ---
    {"q": "deze week", "start": "2026-07-06", "end": "2026-07-13"},
    {"q": "vorige week", "start": "2026-06-29", "end": "2026-07-06"},
    {"q": "last week", "start": "2026-06-29"},
    {"q": "over heel vorige week", "start": "2026-06-29", "end": "2026-07-06"},

    # --- rolling windows without a number ---
    {"q": "afgelopen week", "start": "2026-07-03", "end": "2026-07-10"},
    {"q": "laatste week", "start": "2026-07-03"},
    {"q": "afgelopen maand", "start": "2026-06-10", "end": "2026-07-10"},
    {"q": "afgelopen jaar", "start": "2025-07-10", "end": "2026-07-10"},

    # --- week parts ---
    {"q": "begin vorige week", "start": "2026-06-29", "end": "2026-07-02"},
    {"q": "midden vorige week", "start": "2026-07-01", "end": "2026-07-03"},
    {"q": "eind vorige week", "start": "2026-07-03", "end": "2026-07-06"},
    {"q": "begin deze week", "start": "2026-07-06", "end": "2026-07-09"},

    # --- weekend ---
    {"q": "afgelopen weekend", "start": "2026-07-04", "end": "2026-07-06"},
    {"q": "het weekend", "start": "2026-07-04"},
    {"q": "dit weekend", "start": "2026-07-11", "end": "2026-07-13"},
    {"q": "komend weekend", "start": "2026-07-11"},

    # --- "N unit geleden / ago / terug" ---
    {"q": "een week geleden", "start": "2026-07-02", "end": "2026-07-03"},
    {"q": "precies een week geleden", "start": "2026-07-02"},
    {"q": "twee weken geleden", "start": "2026-06-25"},
    {"q": "2 weken geleden", "start": "2026-06-25"},
    {"q": "3 dagen geleden", "start": "2026-07-06"},
    {"q": "drie dagen geleden", "start": "2026-07-06"},
    {"q": "een maand geleden", "start": "2026-06-09"},
    {"q": "one week ago", "start": "2026-07-02"},
    {"q": "5 days ago", "start": "2026-07-04"},
    {"q": "twee weken terug", "start": "2026-06-25"},

    # --- whole relative months ---
    {"q": "deze maand", "start": "2026-07-01", "end": "2026-08-01"},
    {"q": "vorige maand", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "last month", "start": "2026-06-01"},

    # --- month by name (year inferred = most recent past) ---
    {"q": "april", "start": "2026-04-01", "end": "2026-05-01"},
    {"q": "mei 2026", "start": "2026-05-01", "end": "2026-06-01"},
    {"q": "december", "start": "2025-12-01", "end": "2026-01-01"},   # future month -> last year
    {"q": "juli", "start": "2026-07-01", "end": "2026-08-01"},
    {"q": "begin april", "start": "2026-04-01", "end": "2026-04-11"},
    {"q": "midden juni", "start": "2026-06-11", "end": "2026-06-21"},
    {"q": "eind mei", "start": "2026-05-21", "end": "2026-06-01"},
    {"q": "june", "start": "2026-06-01"},

    # --- YYYY-MM ---
    {"q": "2026-06", "start": "2026-06-01", "end": "2026-07-01"},

    # --- explicit ranges ---
    {"q": "tussen 2026-07-01 en 2026-07-07", "start": "2026-07-01", "end": "2026-07-08"},
    {"q": "van 2026-06-01 tot 2026-06-03", "start": "2026-06-01", "end": "2026-06-04"},
    {"q": "afgelopen 7 dagen", "start": "2026-07-03", "end": "2026-07-10"},
    {"q": "laatste 14 dagen", "start": "2026-06-26", "end": "2026-07-10"},

    # --- topic extraction alongside a period ---
    {"q": "afgelopen week aan otgw 2.0.0", "start": "2026-07-03", "topic": "otgw 2.0.0"},
    {"q": "vorige week over mqtt", "start": "2026-06-29", "topic": "mqtt"},
    {"q": 'onderwerp "release" vorige week', "start": "2026-06-29", "topic": "release"},

    # --- more word-based weekdays ---
    {"q": "afgelopen dinsdag", "start": "2026-07-07"},
    {"q": "afgelopen woensdag", "start": "2026-07-08"},
    {"q": "afgelopen vrijdag", "start": "2026-07-03"},
    {"q": "komende zaterdag", "start": "2026-07-11"},
    {"q": "komende zondag", "start": "2026-07-12"},
    {"q": "deze week zaterdag", "start": "2026-07-11"},
    {"q": "vorige week vrijdag", "start": "2026-07-03"},
    {"q": "vorige week zondag", "start": "2026-07-05"},

    # --- more word-based week parts / weekend ---
    {"q": "begin komende week", "start": "2026-07-13", "end": "2026-07-16"},
    {"q": "eind deze week", "start": "2026-07-10", "end": "2026-07-13"},
    {"q": "vorig weekend", "start": "2026-07-04", "end": "2026-07-06"},
    {"q": "het afgelopen weekend", "start": "2026-07-04"},

    # --- more "geleden" ---
    {"q": "een dag geleden", "start": "2026-07-08"},
    {"q": "twee dagen geleden", "start": "2026-07-07"},
    {"q": "vier weken geleden", "start": "2026-06-11"},
    {"q": "afgelopen 30 dagen", "start": "2026-06-10", "end": "2026-07-10"},
    {"q": "laatste 3 dagen", "start": "2026-07-07", "end": "2026-07-10"},

    # --- more month-by-name ---
    {"q": "begin juli", "start": "2026-07-01", "end": "2026-07-11"},
    {"q": "eind juni", "start": "2026-06-21", "end": "2026-07-01"},
    {"q": "midden mei", "start": "2026-05-11", "end": "2026-05-21"},
    {"q": "may 2026", "start": "2026-05-01", "end": "2026-06-01"},
    {"q": "march", "start": "2026-03-01", "end": "2026-04-01"},

    # --- weekday range + named-date range ---
    {"q": "van maandag tot vrijdag", "start": "2026-07-06", "end": "2026-07-11"},

    # =====================================================================
    # Multi-language cases (nl/en above, de/fr/es/it below). Same anchors:
    #   today=2026-07-09 (Thu)  this Mon=2026-07-06  last Mon=2026-06-29
    #   Friday this-week=07-10, most-recent-past Friday=07-03
    # Post-positioned modifiers ("vendredi dernier", "viernes pasado",
    # "venerdì scorso") resolve via the bare-weekday past default; that is why
    # they land on 2026-07-03. Heavily inflected/future post-positioned forms
    # are left to a future dateparser layer.
    # =====================================================================

    # --- Deutsch (de) ---
    {"q": "gestern", "start": "2026-07-08", "end": "2026-07-09"},
    {"q": "letzte woche", "start": "2026-06-29", "end": "2026-07-06"},
    {"q": "diese woche", "start": "2026-07-06", "end": "2026-07-13"},
    {"q": "letzten monat", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "letzten freitag", "start": "2026-07-03", "end": "2026-07-04"},
    {"q": "vor zwei wochen", "start": "2026-06-25"},
    {"q": "märz", "start": "2026-03-01", "end": "2026-04-01"},
    {"q": "wochenende", "start": "2026-07-04", "end": "2026-07-06"},

    # --- Français (fr) ---
    {"q": "hier", "start": "2026-07-08", "end": "2026-07-09"},
    {"q": "la semaine dernière", "start": "2026-06-29", "end": "2026-07-06"},
    {"q": "cette semaine", "start": "2026-07-06", "end": "2026-07-13"},
    {"q": "le mois dernier", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "vendredi dernier", "start": "2026-07-03"},
    {"q": "il y a deux semaines", "start": "2026-06-25"},
    {"q": "avril", "start": "2026-04-01", "end": "2026-05-01"},
    {"q": "week-end", "start": "2026-07-04", "end": "2026-07-06"},

    # --- Español (es) ---
    {"q": "ayer", "start": "2026-07-08", "end": "2026-07-09"},
    {"q": "la semana pasada", "start": "2026-06-29", "end": "2026-07-06"},
    {"q": "esta semana", "start": "2026-07-06", "end": "2026-07-13"},
    {"q": "el mes pasado", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "el viernes pasado", "start": "2026-07-03"},
    {"q": "hace dos semanas", "start": "2026-06-25"},
    {"q": "junio", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "fin de semana", "start": "2026-07-04", "end": "2026-07-06"},

    # --- Italiano (it) ---
    {"q": "ieri", "start": "2026-07-08", "end": "2026-07-09"},
    {"q": "la settimana scorsa", "start": "2026-06-29", "end": "2026-07-06"},
    {"q": "questa settimana", "start": "2026-07-06", "end": "2026-07-13"},
    {"q": "il mese scorso", "start": "2026-06-01", "end": "2026-07-01"},
    {"q": "venerdì scorso", "start": "2026-07-03"},
    {"q": "due settimane fa", "start": "2026-06-25"},
    {"q": "maggio", "start": "2026-05-01", "end": "2026-06-01"},
    {"q": "fine settimana", "start": "2026-07-04", "end": "2026-07-06"},

    # --- error / ambiguous ---
    {"q": "", "start": "2026-07-09"},          # empty -> default today
    {"q": "ooit", "ok": False},                # unrecognisable
    {"q": "01/02/2026", "ok": False},          # ambiguous numeric date
]

# Layer 2 (dateparser) fallback: languages NOT in the deterministic locale
# layer. Only run when dateparser is installed; ranges are snapped from
# dateparser's own `period` granularity (week/month -> calendar range).
_HAS_DP = bool(_activity._get_dateparser())
LAYER2_CASES: list[dict] = [
    {"q": "wczoraj", "start": "2026-07-08", "end": "2026-07-09"},            # pl yesterday
    {"q": "w zeszłym tygodniu", "start": "2026-06-29", "end": "2026-07-06"}, # pl last week (week-snap)
    {"q": "w zeszłym miesiącu", "start": "2026-06-01", "end": "2026-07-01"}, # pl last month
    {"q": "semana passada", "start": "2026-06-29", "end": "2026-07-06"},     # pt last week
    {"q": "förra veckan", "start": "2026-06-29", "end": "2026-07-06"},       # sv last week
    {"q": "на прошлой неделе", "start": "2026-06-29", "end": "2026-07-06"},  # ru last week
    {"q": "geçen hafta", "start": "2026-06-29", "end": "2026-07-06"},        # tr last week
    {"q": "3 marca 2026", "start": "2026-03-03", "end": "2026-03-04"},       # pl accented named date
]


def _check(case: dict) -> list[str]:
    p = _activity.parse_period(case["q"], now=NOW)
    errs: list[str] = []
    want_ok = case.get("ok", True)
    if p.ok != want_ok:
        return [f"ok={p.ok} want {want_ok} (error={p.error!r})"]
    if not want_ok:
        return errs
    if "start" in case and p.start[:10] != case["start"]:
        errs.append(f"start={p.start[:10]} want {case['start']}")
    if "end" in case and p.end_exclusive[:10] != case["end"]:
        errs.append(f"end={p.end_exclusive[:10]} want {case['end']}")
    if "topic" in case:
        got = _activity._clean_topic(p.topic)
        if got != case["topic"]:
            errs.append(f"topic={got!r} want {case['topic']!r}")
    return errs


def _active_cases() -> list[dict]:
    return CASES + (LAYER2_CASES if _HAS_DP else [])


def run() -> int:
    passed = 0
    failed = 0
    for case in _active_cases():
        errs = _check(case)
        if errs:
            failed += 1
            print(f"FAIL [{case['q']!r}]: {'; '.join(errs)}")
        else:
            passed += 1
    # Layer 3 (LLM) hermetic check — stubbed, no live model.
    llm_errs = _check_llm_layer()
    if llm_errs:
        failed += 1
        print(f"FAIL [llm-layer]: {'; '.join(llm_errs)}")
    else:
        passed += 1
    skipped = 0 if _HAS_DP else len(LAYER2_CASES)
    tail = f", {skipped} skipped (dateparser absent)" if skipped else ""
    total = len(_active_cases()) + 1  # + the llm-layer check
    print(f"\ntemporal test set: {passed} passed, {failed} failed, {total} total{tail}")
    return 0 if failed == 0 else 1


def test_temporal_cases():
    """pytest entry point: fail on the first broken case."""
    broken = [(c["q"], _check(c)) for c in _active_cases()]
    broken = [(q, e) for q, e in broken if e]
    assert not broken, "\n".join(f"{q!r}: {'; '.join(e)}" for q, e in broken)


def _check_llm_layer() -> list[str]:
    """Hermetic check of Layer 3 (LLM fallback): stubbed call + in-memory cache,
    no live model, no DB. Verifies flag-off bypass, resolution, cache-hit
    (single call), and graceful handling of invalid model output."""
    errs: list[str] = []
    orig = {k: getattr(_activity, k) for k in
            ("_llm_enabled", "_llm_call", "_llm_cache_get", "_llm_cache_put", "_llm_audit")}
    try:
        phrase = "een volstrekt onbekende compositionele testfrase qqq"
        # 1. flag OFF (default) -> Layer 3 must not fire; exotic phrase errors.
        _activity._llm_enabled = lambda: False
        if _activity.parse_period(phrase, now=NOW).ok:
            errs.append("flag-off: exotic phrase unexpectedly resolved")
        # 2. flag ON + stub -> resolves canned JSON with low confidence.
        calls = [0]
        store: dict = {}
        _activity._llm_enabled = lambda: True
        def fake(prompt, **k):
            calls[0] += 1
            return '{"start":"2026-07-04","end":"2026-07-06","granularity":"range"}'
        _activity._llm_call = fake
        _activity._llm_cache_get = lambda v, key: store.get(key)
        _activity._llm_cache_put = lambda v, key, ph, r, s, e, g: store.__setitem__(key, (s, e, g))
        _activity._llm_audit = lambda v, e: None
        p = _activity.parse_period(phrase, now=NOW)
        if not (p.ok and p.start[:10] == "2026-07-04" and p.end_exclusive[:10] == "2026-07-06"):
            errs.append(f"llm resolve wrong: ok={p.ok} {p.start[:10]}..{p.end_exclusive[:10]}")
        if abs(p.confidence - 0.4) > 1e-9:
            errs.append(f"llm confidence={p.confidence} want 0.4")
        # 3. cache hit -> no second model call.
        _activity.parse_period(phrase, now=NOW)
        if calls[0] != 1:
            errs.append(f"cache miss: model called {calls[0]}x, want 1")
        # 4. invalid model output -> graceful error, no crash.
        store.clear()
        _activity._llm_call = lambda prompt, **k: "not json at all"
        if _activity.parse_period(phrase, now=NOW).ok:
            errs.append("bad-json: unexpectedly resolved")
    finally:
        for k, v in orig.items():
            setattr(_activity, k, v)
    return errs


def test_llm_layer():
    errs = _check_llm_layer()
    assert not errs, "; ".join(errs)


if __name__ == "__main__":
    raise SystemExit(run())
