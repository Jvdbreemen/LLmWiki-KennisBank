"""Tests for scene diagnostics and the oracle ceiling (TASK-134).

The ceiling decides whether an arm is worth running at all, so an optimistic
bug here would send the experiment chasing a gain that cannot exist.
"""
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _scenes  # noqa: E402


def _load(filename):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""), str(SCRIPTS / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.rep = _load("scene-report.py")
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self._tmp.name) / "kb-scene.db"))
        _scenes.ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_reports_shape_and_coverage(self):
        _scenes.write_scenes(self.conn, "community", [
            ("a", ["1.md", "2.md", "3.md"], [1.0, 0.0]),
            ("b", ["4.md"], [0.0, 1.0]),
        ])
        d = self.rep.diagnostics(self.conn, total_memories=8)
        self.assertEqual(d["scenes"], 2)
        self.assertEqual(d["largest"], 3)
        self.assertEqual(d["singletons"], 1)
        self.assertEqual(d["covered"], 4)
        self.assertAlmostEqual(d["coverage"], 0.5, places=9)

    def test_empty_store_is_all_zero(self):
        d = self.rep.diagnostics(self.conn, total_memories=8)
        self.assertEqual(d["scenes"], 0)
        self.assertEqual(d["coverage"], 0.0)


class OracleCeilingTest(unittest.TestCase):
    """Only a miss whose gold shares a scene with a retrieved hit is reachable."""

    def setUp(self):
        self.rep = _load("scene-report.py")
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self._tmp.name) / "kb-scene.db"))
        _scenes.ensure_schema(self.conn)
        _scenes.write_scenes(self.conn, "community", [
            ("s1", ["gold.md", "top.md"], [1.0, 0.0]),
            ("s2", ["other.md", "far.md"], [0.0, 1.0]),
        ])

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_miss_in_the_same_scene_as_a_hit_is_reachable(self):
        results = [{"expect": ["gold"], "rank": 0, "hits": ["top"]}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["misses"], 1)
        self.assertEqual(out["reachable"], 1)
        self.assertAlmostEqual(out["ceiling_recall"], 1.0, places=9)

    def test_miss_in_a_different_scene_is_unreachable(self):
        results = [{"expect": ["far"], "rank": 0, "hits": ["top"]}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["reachable"], 0)
        self.assertAlmostEqual(out["ceiling_recall"], 0.0, places=9)

    def test_a_question_already_answered_is_not_counted(self):
        """The prior can only add; it cannot improve a question already hit."""
        results = [{"expect": ["gold"], "rank": 2, "hits": ["top", "gold"]}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["misses"], 0)
        self.assertEqual(out["reachable"], 0)
        self.assertAlmostEqual(out["ceiling_recall"], 1.0, places=9)

    def test_a_miss_with_no_retrieved_hits_is_unreachable(self):
        """With nothing retrieved there is no scene to route from."""
        results = [{"expect": ["gold"], "rank": 0, "hits": []}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["reachable"], 0)

    def test_gold_outside_every_scene_is_unreachable(self):
        results = [{"expect": ["unclustered"], "rank": 0, "hits": ["top"]}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["reachable"], 0)

    def test_rank_beyond_k_counts_as_a_miss(self):
        results = [{"expect": ["gold"], "rank": 9, "hits": ["top"]}]
        out = self.rep.oracle_ceiling(self.conn, results)
        self.assertEqual(out["misses"], 1)
        self.assertEqual(out["reachable"], 1)


if __name__ == "__main__":
    unittest.main()
