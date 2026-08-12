"""The scene prior on the recall path, and the parity gate (TASK-134).

The parity test is the one that matters: with the prior off, the code must take
the baseline path exactly. If it does not, every arm measured afterwards is
comparing against something other than the baseline, and no number in the
report means anything.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(filename):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_").replace(".py", ""), str(SCRIPTS / filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(path, score, cos=None):
    return {"path": path, "layer": "memory", "score": score,
            "cos": score if cos is None else cos, "title": "", "created": "",
            "fts": False}


class MergeSceneMembersTest(unittest.TestCase):
    """Pure merge logic: additive, never reordering, never re-scoring."""

    def setUp(self):
        self.kb = _load("kb-recall.py")

    def test_admits_a_member_that_missed_the_floor(self):
        primary = [_row("09-memory/a.md", 0.80)]
        wide = primary + [_row("09-memory/b.md", 0.38), _row("09-memory/z.md", 0.37)]
        merged = self.kb._merge_scene_members(
            primary, wide, members={"09-memory/b.md"}, boost=0.05)
        self.assertEqual([r["path"] for r in merged],
                         ["09-memory/a.md", "09-memory/b.md"])
        self.assertIs(merged[1]["scene"], True)
        self.assertAlmostEqual(merged[1]["score"], 0.43, places=9)

    def test_non_members_are_never_admitted(self):
        primary = [_row("09-memory/a.md", 0.80)]
        wide = primary + [_row("09-memory/z.md", 0.44)]
        merged = self.kb._merge_scene_members(primary, wide, members=set(), boost=0.5)
        self.assertEqual([r["path"] for r in merged], ["09-memory/a.md"])

    def test_a_primary_hit_is_never_rescored(self):
        primary = [_row("09-memory/a.md", 0.80)]
        wide = primary + [_row("09-memory/b.md", 0.39)]
        merged = self.kb._merge_scene_members(
            primary, wide, members={"09-memory/a.md"}, boost=0.5)
        self.assertEqual(merged[0]["path"], "09-memory/a.md")
        self.assertEqual(merged[0]["score"], 0.80)
        self.assertNotIn("scene", merged[0])

    def test_baseline_rows_are_a_prefix_of_the_result(self):
        """The property the parity claim rests on: treatment ⊇ baseline."""
        primary = [_row("09-memory/a.md", 0.80), _row("09-memory/b.md", 0.60)]
        wide = primary + [_row("09-memory/c.md", 0.36)]
        merged = self.kb._merge_scene_members(
            primary, wide, members={"09-memory/c.md"}, boost=0.0)
        self.assertEqual([r["path"] for r in merged[:2]],
                         [r["path"] for r in primary])


class ScenePriorFailOpenTest(unittest.TestCase):
    """Every failure mode must degrade to 'no members', i.e. to baseline."""

    def setUp(self):
        self.kb = _load("kb-recall.py")

    def test_missing_database_yields_no_members(self):
        import _scenes
        original = _scenes.scene_index_path
        _scenes.scene_index_path = lambda: Path("does-not-exist-kb-scene.db")
        try:
            self.assertEqual(
                self.kb._scene_members_for([{"path": "x.md"}], {"floor": 0.35}), set())
        finally:
            _scenes.scene_index_path = original

    def test_exception_yields_no_members(self):
        import _scenes

        def boom():
            raise RuntimeError("disk on fire")

        original = _scenes.scene_index_path
        _scenes.scene_index_path = boom
        try:
            self.assertEqual(
                self.kb._scene_members_for([{"path": "x.md"}], {"floor": 0.35}), set())
        finally:
            _scenes.scene_index_path = original


class SceneRoutingTest(unittest.TestCase):
    """The scene is chosen by membership of the top hits, not by centroid.

    Centroid matching was the first implementation and failed on real data: a
    centroid over ~19 atomic memories averages into a generic direction, and
    the winning scene contained none of the twenty nearest memories on any of
    856 questions. Routing from the top hit is both correct and cheaper.
    """

    def setUp(self):
        import sqlite3
        import tempfile
        import _scenes
        self.kb = _load("kb-recall.py")
        self._scenes = _scenes
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "kb-scene.db"
        conn = sqlite3.connect(str(self.db))
        _scenes.ensure_schema(conn)
        _scenes.write_scenes(conn, "community", [
            ("s1", ["/v/09-memory/top.md", "/v/09-memory/sibling.md"], [1.0, 0.0]),
            ("s2", ["/v/09-memory/other.md"], [0.0, 1.0]),
        ])
        index = Path(self._tmp.name) / "kb-index.db"
        index.write_bytes(b"x")
        _scenes.set_fingerprint(conn, _scenes.fingerprint(index))
        conn.close()
        self._saved_path = _scenes.scene_index_path
        self._saved_index = self.kb._kbindex.index_path
        _scenes.scene_index_path = lambda: self.db
        self.kb._kbindex.index_path = staticmethod(lambda: index)

    def tearDown(self):
        self._scenes.scene_index_path = self._saved_path
        self.kb._kbindex.index_path = self._saved_index
        self._tmp.cleanup()

    def test_routes_from_the_top_hit(self):
        members = self.kb._scene_members_for(
            [_row("/v/09-memory/top.md", 0.8)], {"floor": 0.35})
        self.assertEqual(members,
                         {"/v/09-memory/top.md", "/v/09-memory/sibling.md"})

    def test_a_top_hit_outside_every_scene_yields_nothing(self):
        members = self.kb._scene_members_for(
            [_row("/v/09-memory/unclustered.md", 0.8)], {"floor": 0.35})
        self.assertEqual(members, set())

    def test_seeds_limits_how_many_hits_may_nominate(self):
        rows = [_row("/v/09-memory/top.md", 0.8),
                _row("/v/09-memory/other.md", 0.7)]
        one = self.kb._scene_members_for(rows, {"seeds": 1})
        two = self.kb._scene_members_for(rows, {"seeds": 2})
        self.assertNotIn("/v/09-memory/other.md", one)
        self.assertIn("/v/09-memory/other.md", two)

    def test_no_primary_hits_means_no_scene(self):
        self.assertEqual(self.kb._scene_members_for([], {"floor": 0.35}), set())


class RecallHitsHarness:
    """Run recall_hits with every collaborator faked out.

    An earlier version of these tests faked only the index, which left the
    scene member set empty in every case -- so a mutation that always took the
    scene branch passed unnoticed. The prior can only be tested when the fakes
    can actually produce members, which means faking the rerank, the status
    recheck and the snippet reader too.
    """

    def __init__(self, kb, primary, wide, members):
        self.kb = kb
        self.primary = primary
        self.wide = wide
        self.members = set(members)
        self.searches = []
        self.member_lookups = 0
        self._saved = {}

    def __enter__(self):
        kb = self.kb
        harness = self

        class FakeIndex:
            @staticmethod
            def index_path():
                return Path("kb-index.db")

            @staticmethod
            def is_valid_for(conn, embed_id):
                return True

            @staticmethod
            def search(conn, **kw):
                harness.searches.append(kw)
                return (list(harness.wide) if len(harness.searches) > 1
                        else list(harness.primary))

        class FakeMem:
            @staticmethod
            def read_status(path):
                return "current"

        class FakeEmb:
            @staticmethod
            def doc_text(path, cap=280):
                return "snippet"

            @staticmethod
            def embed_id():
                return "fake"

        class FakeRank:
            @staticmethod
            def rerank(rows, *a, **kw):
                return list(rows)

        def members_for(rows_primary, prior):
            harness.member_lookups += 1
            return set(harness.members)

        for name, value in (("_kbindex", FakeIndex), ("_mem", FakeMem),
                            ("emb", FakeEmb), ("_rank", FakeRank),
                            ("_open_ro", lambda p: object()),
                            ("_scene_members_for", members_for),
                            ("_coupling_sources_fn", lambda conn, rows: None)):
            self._saved[name] = getattr(kb, name, None)
            setattr(kb, name, value)
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            if value is None:
                try:
                    delattr(self.kb, name)
                except Exception:
                    pass
            else:
                setattr(self.kb, name, value)
        return False


class ParityTest(unittest.TestCase):
    """scene_prior=None must take the baseline path, unchanged."""

    def setUp(self):
        self.kb = _load("kb-recall.py")
        self.primary = [_row("09-memory/a.md", 0.80)]
        self.wide = self.primary + [_row("09-memory/b.md", 0.38)]

    def test_no_prior_never_consults_the_scene_store(self):
        with RecallHitsHarness(self.kb, self.primary, self.wide,
                               members={"09-memory/b.md"}) as h:
            out = self.kb.recall_hits([0.1] * 8, query_text="x", k=3,
                                      layers=("memory",), scene_prior=None)
        self.assertEqual(len(h.searches), 1,
                         "scene_prior=None must not issue a second search")
        self.assertEqual(h.member_lookups, 0,
                         "scene_prior=None must not touch the scene store")
        self.assertEqual([r["path"] for r in out], ["09-memory/a.md"])

    def test_prior_admits_a_member_through_the_full_path(self):
        with RecallHitsHarness(self.kb, self.primary, self.wide,
                               members={"09-memory/b.md"}) as h:
            out = self.kb.recall_hits([0.1] * 8, query_text="x", k=3,
                                      layers=("memory",),
                                      scene_prior={"floor": 0.35, "boost": 0.0})
        self.assertEqual(len(h.searches), 2)
        self.assertEqual([r["path"] for r in out],
                         ["09-memory/a.md", "09-memory/b.md"])

    def test_prior_without_members_issues_exactly_one_search(self):
        with RecallHitsHarness(self.kb, self.primary, self.wide,
                               members=set()) as h:
            self.kb.recall_hits([0.1] * 8, query_text="x", k=3,
                                layers=("memory",),
                                scene_prior={"floor": 0.35, "boost": 0.0})
        self.assertEqual(len(h.searches), 1)

    def test_result_is_never_longer_than_k(self):
        """The prior may win a slot; it may never enlarge the injected block.

        Without the post-rerank cut, admitted members are appended on top of a
        full baseline set and the hook would inject more lines than top_n --
        silently, and only on queries that happen to match a scene.
        """
        primary = [_row(f"09-memory/p{i}.md", 0.9 - i * 0.1) for i in range(3)]
        extra = [_row(f"09-memory/s{i}.md", 0.36) for i in range(4)]
        with RecallHitsHarness(self.kb, primary, primary + extra,
                               members={r["path"] for r in extra}):
            out = self.kb.recall_hits([0.1] * 8, query_text="x", k=3,
                                      layers=("memory",),
                                      scene_prior={"floor": 0.35, "boost": 0.0})
        self.assertEqual(len(out), 3)


if __name__ == "__main__":
    unittest.main()
