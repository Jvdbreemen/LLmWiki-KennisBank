"""The L2 scene layer is gone, and stays gone until a measurement says otherwise.

TASK-134 measured a scenario tier between atomic memories and wiki articles
against a winner rule fixed in advance, and all four conditions failed on the
best arm: recall@5 +0.000 where +0.02 was required, recall@1 -0.006 where no
decrease was required, p50 +65 ms where +5 ms was the ceiling, and a gain in
1 of 4 memory_type groups where 2 were required. ADR-008 records the removal.

These are guard tests, not behaviour tests. They exist because the thing they
guard is attractive: the same research measured an oracle ceiling of +0.040
recall@5 (p < 0.0001), so "scenes could help" is true and will be proposed
again. What failed was every available clusterer, and re-adding the plumbing
without a clusterer that beats graph communities by roughly fivefold re-creates
an inert branch in the hot-path read library.

If a future measurement clears the winner rule, delete this file in the same
change that re-adds the layer. A guard that outlives its reason is worse than
no guard.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402


class RecallHasNoScenePriorTest(unittest.TestCase):
    """The hot-path read library carries no scene plumbing.

    This is the half that actually cost something: `scene_prior` threaded
    through `recall_hits` and `memory_hits`, so every later change to recall
    had to reason around a branch no production path reached.
    """

    def setUp(self):
        self.kb_recall = load_script("kb-recall.py")

    def test_recall_hits_takes_no_scene_prior(self):
        params = inspect.signature(self.kb_recall.recall_hits).parameters
        self.assertNotIn("scene_prior", params)

    def test_memory_hits_takes_no_scene_prior(self):
        params = inspect.signature(self.kb_recall.memory_hits).parameters
        self.assertNotIn("scene_prior", params)

    def test_no_scene_helpers_remain(self):
        for gone in ("_scene_path", "_merge_scene_members", "_scene_members_for"):
            self.assertFalse(hasattr(self.kb_recall, gone),
                             f"kb-recall still defines {gone}")


class SceneModulesAreGoneTest(unittest.TestCase):
    def test_no_scene_scripts_ship(self):
        found = sorted(p.name for p in SCRIPTS.glob("*scene*"))
        self.assertEqual(found, [], f"scene scripts still present: {found}")

    def test_querycache_survives_its_origin(self):
        """`_querycache.py` was extracted from the scene experiment (TASK-190)
        and is now shared by rank-factors and rerank-ceiling. Removing the
        scene layer must not take it along."""
        self.assertTrue((SCRIPTS / "_querycache.py").exists())


class SceneTogglesAreGoneTest(unittest.TestCase):
    def test_settings_has_no_scene_toggle(self):
        import _settings
        self.assertNotIn("scene_retrieval", _settings.DEFAULTS)

    def test_retrieve_reads_no_scene_knobs(self):
        src = (SCRIPTS / "kb-retrieve.py").read_text(encoding="utf-8")
        for knob in ("scene_retrieval", "scene_clusterer",
                     "scene_floor", "scene_boost"):
            self.assertNotIn(knob, src, f"kb-retrieve.py still names {knob}")


class TheEvidenceSurvivesTest(unittest.TestCase):
    """Delete the code, keep the reason. Without the report a future reader
    sees only an absent feature and rebuilds it."""

    def test_research_report_is_kept(self):
        self.assertTrue(
            (REPO_ROOT / "docs" / "research" / "l2-scene-retrieval-2026-08.md").exists())

    def test_adr_records_the_removal(self):
        adrs = list((REPO_ROOT / "docs" / "adr").glob("*scene*"))
        self.assertTrue(adrs, "no ADR documents the scene-layer removal")


if __name__ == "__main__":
    unittest.main()
