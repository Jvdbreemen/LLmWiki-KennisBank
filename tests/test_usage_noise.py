"""Tests voor het mens-gated noise-signaal (TASK-17): _usage.mark_noise/noise_of,
de schema-migratie op een bestaande db, en _rank.noise_factor + rerank-wiring.

Sqlite naar temp-vault; geen model, geen hooks.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class NoiseCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = self.tmp.name
        self.addCleanup(self._restore)
        import _rank
        import _usage
        self.u = _usage
        self.r = _rank

    def _restore(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved


class TestNoiseStore(NoiseCase):
    def test_mark_noise_counts_and_noise_of(self):
        self.u.log_injected(["doc-x"], today="2026-07-01")
        self.u.log_injected(["doc-x"], today="2026-07-02")
        self.assertEqual(self.u.mark_noise(["doc-x"], today="2026-07-03"), 1)
        self.assertEqual(self.u.noise_of("doc-x"), (1, 2))

    def test_noise_of_unknown_stem_is_zero(self):
        self.assertEqual(self.u.noise_of("bestaat-niet"), (0, 0))

    def test_migration_adds_columns_to_pre_noise_db(self):
        # Bouw een db met het OUDE schema (zonder noise-kolommen), zoals elke
        # bestaande installatie die heeft, en controleer dat _connect migreert.
        db = Path(self.tmp.name) / ".claude" / "kb-usage.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db))
        conn.executescript(
            "CREATE TABLE usage (stem TEXT PRIMARY KEY, injected INTEGER NOT NULL "
            "DEFAULT 0, used INTEGER NOT NULL DEFAULT 0, last_injected TEXT, "
            "last_used TEXT);")
        conn.execute("INSERT INTO usage(stem, injected) VALUES('oud-doc', 5)")
        conn.commit()
        conn.close()
        self.assertEqual(self.u.mark_noise(["oud-doc"], today="2026-07-14"), 1)
        self.assertEqual(self.u.noise_of("oud-doc"), (1, 5))


class TestNoiseFactor(NoiseCase):
    def test_zero_noise_is_exactly_neutral(self):
        self.assertEqual(self.r.noise_factor(0, 10), 1.0)
        self.assertEqual(self.r.noise_factor(0, 0), 1.0)
        self.assertEqual(self.r.noise_factor(3, 0), 1.0)

    def test_penalty_scales_with_rate_and_is_floored(self):
        # 1 markering op 10 injecties: kleine aftrek
        self.assertAlmostEqual(self.r.noise_factor(1, 10), 0.98)
        # 100% noise-rate: maximale aftrek, exact de vloer
        self.assertAlmostEqual(self.r.noise_factor(5, 5), 0.80)
        # rate > 1 (meer markeringen dan injecties) blijft op de vloer
        self.assertAlmostEqual(self.r.noise_factor(12, 5), 0.80)

    def test_rerank_demotes_marked_noise(self):
        hits = [
            {"path": "02-wiki/ruis.md", "layer": "wiki", "score": 1.0},
            {"path": "02-wiki/nuttig.md", "layer": "wiki", "score": 0.9},
        ]
        noise = {"ruis": (4, 4), "nuttig": (0, 4)}
        out = self.r.rerank(hits, lambda p: {}, noise_fn=lambda s: noise.get(s, (0, 0)))
        self.assertEqual(Path(out[0]["path"]).stem, "nuttig")
        self.assertAlmostEqual(out[1]["score"], 0.80)

    def test_rerank_without_noise_fn_is_unchanged(self):
        hits = [{"path": "02-wiki/a.md", "layer": "wiki", "score": 0.7}]
        out = self.r.rerank(hits, lambda p: {})
        self.assertAlmostEqual(out[0]["score"], 0.7)


if __name__ == "__main__":
    unittest.main()
