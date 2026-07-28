"""Tests voor scripts/wiki-scan.py — deterministische /wiki-kandidaten (TASK-89 D2).

Zonder model: similar_fn geinjecteerd. De harde eisen: determinisme (twee runs
identiek), gesloten actieset met fail-safe default, en de scanned_logs-guard
(0 kandidaten uit N logs != 0 uit 0).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from tests._loader import load_script


def _ws():
    return load_script("wiki-scan.py")


class WikiScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "01-raw" / "sessies").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.ws = _ws()
        self.today = date.today().isoformat()

    def _log(self, name_date, body):
        base = self.vault / "01-raw" / "sessies"
        i = 0
        p = base / f"raw-sessie-{name_date}-x{i}.md"
        while p.exists():
            i += 1
            p = base / f"raw-sessie-{name_date}-x{i}.md"
        p.write_text(body, encoding="utf-8")
        return p

    def _memory(self, stem, title, promote=True, status="current"):
        (self.vault / "09-memory" / f"{stem}.md").write_text(
            f"---\ntitle: '{title}'\nstatus: {status}\n"
            f"promote_candidate: {'true' if promote else 'false'}\n---\n\nX.\n",
            encoding="utf-8")

    # --- determinisme ---

    def test_two_runs_identical(self):
        self._log(self.today, "wiki-kandidaat: WireGuard opzetten\n")
        a = self.ws.scan(self.vault, similar_fn=lambda t: None)
        b = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertEqual(a, b)

    # --- bronnen ---

    def test_marker_candidate_found(self):
        self._log(self.today, "notities\nwiki-kandidaat: [WireGuard achter CGNAT]\n")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertEqual(r["total"], 1)
        c = r["candidates"][0]
        self.assertEqual(c["topic"], "WireGuard achter CGNAT")
        self.assertEqual(c["source_kind"], "marker")
        self.assertEqual(c["suggested_action"], "nieuw")

    def test_old_logs_outside_window_ignored(self):
        old = (date.today() - timedelta(days=30)).isoformat()
        self._log(old, "wiki-kandidaat: verouderd onderwerp\n")
        r = self.ws.scan(self.vault, days=7, similar_fn=lambda t: None)
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["scanned_logs"], 0)

    def test_cluster_candidate_from_promote_memory(self):
        self._memory("m1", "SQLite WAL strategie")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        kinds = {c["source_kind"] for c in r["candidates"]}
        self.assertIn("cluster", kinds)

    def test_non_current_promote_memory_ignored(self):
        self._memory("m2", "Oud ding", status="retracted")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertEqual(r["total"], 0)

    def test_recurrent_heading_needs_two_logs(self):
        self._log(self.today, "## Traefik configuratie\ninhoud\n")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertEqual(r["total"], 0)  # één log is geen recurrentie
        self._log(self.today, "## Traefik configuratie\nandere sessie\n")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        topics = {c["topic"] for c in r["candidates"]}
        self.assertIn("Traefik configuratie", topics)
        c = [x for x in r["candidates"] if x["topic"] == "Traefik configuratie"][0]
        self.assertEqual(c["source_kind"], "recurrent")
        self.assertEqual(len(c["evidence"]), 2)

    def test_generic_template_headings_excluded(self):
        for _ in range(2):
            self._log(self.today, "## Sessie-herkomst\n## Verbanden\ninhoud\n")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertEqual(r["total"], 0)

    # --- actieset ---

    def test_above_threshold_suggests_herschrijf(self):
        self._log(self.today, "wiki-kandidaat: bestaand onderwerp\n")
        sim = {"path": "02-wiki/x.md", "score": 0.81, "above_threshold": True}
        r = self.ws.scan(self.vault, similar_fn=lambda t: sim)
        self.assertEqual(r["candidates"][0]["suggested_action"], "herschrijf")

    def test_below_threshold_marker_suggests_nieuw(self):
        self._log(self.today, "wiki-kandidaat: nieuw onderwerp\n")
        sim = {"path": None, "score": 0.2, "above_threshold": False}
        r = self.ws.scan(self.vault, similar_fn=lambda t: sim)
        self.assertEqual(r["candidates"][0]["suggested_action"], "nieuw")

    def test_action_always_in_closed_set(self):
        self._log(self.today, "wiki-kandidaat: iets\n## Onderwerp A\n")
        self._log(self.today, "## Onderwerp A\n")
        for sim in (None, {"above_threshold": False, "score": 0.0},
                    {"above_threshold": True, "score": 0.9}):
            r = self.ws.scan(self.vault, similar_fn=lambda t, s=sim: s)
            for c in r["candidates"]:
                self.assertIn(c["suggested_action"], self.ws.ACTIONS)

    def test_suggest_action_falls_back_on_invalid(self):
        action, _ = self.ws.suggest_action("onbekend-soort", 0, None)
        self.assertIn(action, self.ws.ACTIONS)

    # --- guards ---

    def test_scanned_logs_distinguishes_empty_from_none(self):
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertTrue(r["empty"])
        self.assertEqual(r["scanned_logs"], 0)
        self._log(self.today, "gewone notities zonder kandidaten\n")
        r = self.ws.scan(self.vault, similar_fn=lambda t: None)
        self.assertFalse(r["empty"])
        self.assertEqual(r["scanned_logs"], 1)
        self.assertEqual(r["total"], 0)

    def test_topic_filter(self):
        self._log(self.today, "wiki-kandidaat: WireGuard\nwiki-kandidaat: Traefik\n")
        r = self.ws.scan(self.vault, topic_filter="wire", similar_fn=lambda t: None)
        self.assertEqual([c["topic"] for c in r["candidates"]], ["WireGuard"])


if __name__ == "__main__":
    unittest.main()
