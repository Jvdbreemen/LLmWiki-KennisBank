"""CI unittest wrapper for the multilingual temporal parser.

The deterministic test set lives next to the parser in
``scripts/test_activity_temporal.py`` (so it ships with the deployed scripts and
is runnable standalone/pytest). This module re-exposes those cases to the repo's
``unittest discover`` CI suite so the three temporal layers (locale tables,
dateparser fallback, and the optional LLM path) are exercised and covered.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _activity  # noqa: E402
import test_activity_temporal as tat  # noqa: E402  (scripts-side deterministic cases)

_NOW = datetime(2026, 7, 9, 12, 0)


class MultilingualTemporalTest(unittest.TestCase):
    def test_layer1_deterministic_cases(self):
        """Layer 1: nl/en/de/fr/es/it locale tables, pinned to a fixed now."""
        for case in tat.CASES:
            with self.subTest(q=case["q"]):
                errs = tat._check(case)
                self.assertFalse(errs, f"{case['q']!r}: {'; '.join(errs)}")

    @unittest.skipUnless(tat._HAS_DP, "dateparser not installed")
    def test_layer2_dateparser_fallback(self):
        """Layer 2: dateparser fallback for languages outside the locale set."""
        for case in tat.LAYER2_CASES:
            with self.subTest(q=case["q"]):
                errs = tat._check(case)
                self.assertFalse(errs, f"{case['q']!r}: {'; '.join(errs)}")

    def test_layer3_llm_fallback(self):
        """Layer 3: stubbed LLM last resort (flag-off bypass, resolve, cache,
        graceful bad-output). No live model or DB."""
        errs = tat._check_llm_layer()
        self.assertFalse(errs, "; ".join(errs))

    def test_layer3_real_cache_and_audit(self):
        """Exercise the real Layer-3 cache/audit code paths against a temp vault:
        a stubbed model resolves once, is written to the SQLite cache + audit
        log, and a second call is served from the cache (not the model)."""
        tmp = Path(tempfile.mkdtemp(prefix="kb-llm-"))
        vault = tmp / "Kluis"
        (vault / ".claude").mkdir(parents=True)
        saved = {k: getattr(_activity, k) for k in ("_llm_enabled", "_llm_call", "vault_root")}
        try:
            _activity.vault_root = lambda: vault
            _activity._llm_enabled = lambda: True
            _activity._llm_call = lambda prompt, **k: '{"start":"2026-07-04","end":"2026-07-06","granularity":"range"}'
            phrase = "een exotische compositionele testfrase voor de cache qqq"
            p = _activity.parse_period(phrase, now=_NOW)
            self.assertTrue(p.ok)
            self.assertEqual(p.start[:10], "2026-07-04")
            self.assertEqual(p.end_exclusive[:10], "2026-07-06")
            self.assertTrue((vault / ".claude" / "activity-llm-audit.jsonl").is_file())
            # Second call: even if the model would now answer differently, the
            # cached range wins (deterministic repeat).
            _activity._llm_call = lambda prompt, **k: '{"start":"1999-01-01","end":"1999-01-02","granularity":"day"}'
            p2 = _activity.parse_period(phrase, now=_NOW)
            self.assertEqual(p2.start[:10], "2026-07-04")
        finally:
            for k, v in saved.items():
                setattr(_activity, k, v)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_layer2_absent_degrades_gracefully(self):
        """With dateparser forced unavailable and the LLM off (default), an
        otherwise-unresolvable foreign phrase returns a clean parse error."""
        saved = _activity._DATEPARSER_CLS
        try:
            _activity._DATEPARSER_CLS = False
            p = _activity.parse_period("wczoraj", now=_NOW)  # Polish, Layer-2 only
            self.assertFalse(p.ok)
        finally:
            _activity._DATEPARSER_CLS = saved

    def test_layer3_llm_call_http(self):
        """Exercise the real _llm_call HTTP path (stdlib urllib) with a fake
        Ollama response, plus its fail-soft error branch."""
        import json
        import urllib.request

        class _FakeResp:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        saved = urllib.request.urlopen
        try:
            urllib.request.urlopen = lambda req, timeout=None: _FakeResp(
                json.dumps({"response": '{"start":"2026-07-04"}'}).encode("utf-8")
            )
            self.assertEqual(_activity._llm_call("prompt"), '{"start":"2026-07-04"}')

            def _boom(*a, **k):
                raise OSError("ollama down")

            urllib.request.urlopen = _boom
            self.assertIsNone(_activity._llm_call("prompt"))
        finally:
            urllib.request.urlopen = saved

    def test_range_from_iso_rejects_out_of_range(self):
        """A model answer far outside the reference date is rejected."""
        from datetime import date
        rng = _activity._range_from_iso(
            "2100-01-01", "2100-01-02", "day", "orig", "", _activity.LOCAL_TZ, date(2026, 7, 9)
        )
        self.assertIsNone(rng)


if __name__ == "__main__":
    unittest.main()
