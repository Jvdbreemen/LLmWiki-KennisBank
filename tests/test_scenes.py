"""Tests for the derived L2 scene layer (TASK-134).

Covers the store (schema, centroids, fingerprint) and the clusterers. The
parity test that guards the whole experiment lives with the recall changes.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _scenes  # noqa: E402


def _graph_db(tmp_path, rows):
    """Minimal kb-graph.db stand-in: (source_file, community) node rows."""
    conn = sqlite3.connect(str(Path(tmp_path) / "kb-graph.db"))
    conn.execute("CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, label TEXT, "
                 "source_file TEXT, file_type TEXT, community INTEGER)")
    for i, (src, comm) in enumerate(rows):
        conn.execute("INSERT INTO graph_nodes VALUES (?,?,?,?,?)",
                     (f"n{i}", f"n{i}", src, "md", comm))
    conn.commit()
    return conn


class SceneStoreTest(unittest.TestCase):
    """Schema, centroids, and the staleness fingerprint."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.conn = sqlite3.connect(str(self.tmp / "kb-scene.db"))
        _scenes.ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_roundtrip_scene_and_lookup(self):
        n = _scenes.write_scenes(self.conn, "community", [
            ("alpha", ["09-memory/a.md", "09-memory/b.md"], [1.0, 0.0]),
            ("beta", ["09-memory/c.md"], [0.0, 1.0]),
        ])
        self.assertEqual(n, 2)
        hit = _scenes.best_scene(self.conn, [1.0, 0.0], min_cos=0.5)
        self.assertIsNotNone(hit)
        scene_id, cos = hit
        self.assertGreater(cos, 0.99)
        self.assertEqual(sorted(_scenes.members_of(self.conn, scene_id)),
                         ["09-memory/a.md", "09-memory/b.md"])

    def test_best_scene_respects_threshold(self):
        _scenes.write_scenes(self.conn, "community",
                             [("alpha", ["x.md"], [1.0, 0.0])])
        self.assertIsNone(_scenes.best_scene(self.conn, [0.0, 1.0], min_cos=0.5))

    def test_best_scene_on_empty_store_is_none(self):
        self.assertIsNone(_scenes.best_scene(self.conn, [1.0, 0.0], min_cos=0.0))

    def test_centroid_is_unit_length(self):
        c = _scenes.centroid([[3.0, 0.0], [0.0, 3.0]])
        self.assertLess(abs(sum(x * x for x in c) - 1.0), 1e-9)

    def test_centroid_of_empty_is_empty(self):
        self.assertEqual(_scenes.centroid([]), [])

    def test_write_scenes_replaces_previous_run(self):
        _scenes.write_scenes(self.conn, "community",
                             [("alpha", ["x.md"], [1.0, 0.0])])
        _scenes.write_scenes(self.conn, "community",
                             [("beta", ["y.md"], [0.0, 1.0])])
        rows = self.conn.execute("SELECT label FROM scenes").fetchall()
        self.assertEqual([r[0] for r in rows], ["beta"])
        # members and centroids of the previous run must go with it
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM scene_members").fetchone()[0], 1)
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM scene_centroids").fetchone()[0], 1)

    def test_is_current_tracks_the_index_fingerprint(self):
        index = self.tmp / "kb-index.db"
        index.write_bytes(b"x")
        self.assertFalse(_scenes.is_current(self.conn, index))
        _scenes.set_fingerprint(self.conn, _scenes.fingerprint(index))
        self.assertTrue(_scenes.is_current(self.conn, index))

    def test_is_current_false_after_index_changes(self):
        index = self.tmp / "kb-index.db"
        index.write_bytes(b"x")
        _scenes.set_fingerprint(self.conn, _scenes.fingerprint(index))
        index.write_bytes(b"xxxxxxxxxxxx")
        self.assertFalse(_scenes.is_current(self.conn, index))


class CommunityClustererTest(unittest.TestCase):
    """Grouping by the partition already present in kb-graph.db."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._open = []

    def tearDown(self):
        # Windows holds an exclusive lock on an open sqlite file, so the
        # temporary directory cannot be removed while a connection lives.
        # Closing in tearDown keeps the failure mode off other platforms too.
        for conn in self._open:
            try:
                conn.close()
            except Exception:
                pass
        self._tmp.cleanup()

    def _graph(self, rows):
        conn = _graph_db(self.tmp, rows)
        self._open.append(conn)
        return conn

    def test_groups_by_partition(self):
        g = self._graph([("09-memory/a.md", 1), ("09-memory/b.md", 1),
                                 ("09-memory/c.md", 2)])
        out = _scenes.cluster_community(
            ["09-memory/a.md", "09-memory/b.md", "09-memory/c.md"], g)
        groups = sorted(sorted(v) for v in out.values())
        self.assertEqual(groups, [["09-memory/a.md", "09-memory/b.md"],
                                  ["09-memory/c.md"]])

    def test_drops_paths_absent_from_graph(self):
        g = self._graph([("09-memory/a.md", 1)])
        out = _scenes.cluster_community(["09-memory/a.md", "09-memory/zz.md"], g)
        self.assertEqual([p for v in out.values() for p in v], ["09-memory/a.md"])

    def test_uses_majority_when_file_spans_communities(self):
        g = self._graph([("09-memory/a.md", 1), ("09-memory/a.md", 1),
                                 ("09-memory/a.md", 7)])
        out = _scenes.cluster_community(["09-memory/a.md"], g)
        self.assertEqual(list(out.keys()), ["community-1"])

    def test_tie_breaks_on_the_lowest_community_id(self):
        """A genuine tie: equal node counts in two communities.

        The direction is arbitrary but must be STABLE, or the same vault
        produces different scenes on two runs and the experiment compares
        noise. A majority vote hides the tie-break entirely, so this case
        constructs an actual tie.
        """
        g = self._graph([("09-memory/a.md", 7), ("09-memory/a.md", 2)])
        out = _scenes.cluster_community(["09-memory/a.md"], g)
        self.assertEqual(list(out.keys()), ["community-2"])

    def test_empty_input_is_empty(self):
        g = self._graph([("09-memory/a.md", 1)])
        self.assertEqual(_scenes.cluster_community([], g), {})


class TagsClustererTest(unittest.TestCase):
    """Shared tag within a rolling window; every path in exactly one scene."""

    def test_groups_by_shared_tag_within_the_window(self):
        meta = {
            "a.md": {"tags": ["otgw"], "created": "2026-01-01"},
            "b.md": {"tags": ["otgw"], "created": "2026-02-01"},
            "c.md": {"tags": ["otgw"], "created": "2025-01-01"},
        }
        out = _scenes.cluster_tags(meta, window_days=90)
        groups = sorted(sorted(v) for v in out.values())
        self.assertIn(["a.md", "b.md"], groups)
        self.assertIn(["c.md"], groups)

    def test_every_path_is_assigned_exactly_once(self):
        meta = {"a.md": {"tags": ["x", "y"], "created": "2026-01-01"},
                "b.md": {"tags": ["y"], "created": "2026-01-02"}}
        out = _scenes.cluster_tags(meta, window_days=90)
        assigned = [p for v in out.values() for p in v]
        self.assertEqual(sorted(assigned), ["a.md", "b.md"])
        self.assertEqual(len(assigned), len(set(assigned)),
                         "a path in two scenes would apply the prior twice")

    def test_rarest_tag_wins_the_assignment(self):
        """The common tag would swallow the vault; the rare one is informative."""
        meta = {"a.md": {"tags": ["common", "rare"], "created": "2026-01-01"},
                "b.md": {"tags": ["common"], "created": "2026-01-02"},
                "c.md": {"tags": ["common"], "created": "2026-01-03"}}
        out = _scenes.cluster_tags(meta, window_days=90)
        rare = [label for label in out if label.startswith("rare@")]
        self.assertEqual(len(rare), 1)
        self.assertEqual(out[rare[0]], ["a.md"])

    def test_drops_untagged_paths(self):
        meta = {"a.md": {"tags": [], "created": "2026-01-01"}}
        self.assertEqual(_scenes.cluster_tags(meta, window_days=90), {})

    def test_undated_memories_get_their_own_bucket(self):
        meta = {"a.md": {"tags": ["x"], "created": ""},
                "b.md": {"tags": ["x"], "created": "2026-01-01"}}
        out = _scenes.cluster_tags(meta, window_days=90)
        self.assertIn("x@undated", out)
        self.assertEqual(out["x@undated"], ["a.md"])


class LlmClustererTest(unittest.TestCase):
    """Model-formed scenes under a hard cap. The llm_fn is injected, so no
    model is needed to test the parsing, the cap, or the failure modes."""

    def test_parses_an_assignment(self):
        meta = {"a.md": {"title": "OTGW flash"}, "b.md": {"title": "OTGW wifi"}}
        reply = '{"scenes": [{"label": "otgw", "members": ["a.md", "b.md"]}]}'
        out = _scenes.cluster_llm(meta, llm_fn=lambda p: reply, max_scenes=15)
        self.assertEqual(out, {"otgw": ["a.md", "b.md"]})

    def test_tolerates_prose_around_the_json(self):
        meta = {"a.md": {"title": "x"}}
        reply = ('Sure! Here you go:\n'
                 '{"scenes": [{"label": "s", "members": ["a.md"]}]}\nHope that helps.')
        out = _scenes.cluster_llm(meta, llm_fn=lambda p: reply, max_scenes=15)
        self.assertEqual(out, {"s": ["a.md"]})

    def test_enforces_the_cap_by_merging_not_dropping(self):
        meta = {f"{i}.md": {"title": str(i)} for i in range(4)}
        reply = json.dumps({"scenes": [
            {"label": f"s{i}", "members": [f"{i}.md"]} for i in range(4)]})
        out = _scenes.cluster_llm(meta, llm_fn=lambda p: reply, max_scenes=2)
        self.assertLessEqual(len(out), 2)
        self.assertEqual(sorted(p for v in out.values() for p in v),
                         ["0.md", "1.md", "2.md", "3.md"])

    def test_fails_open_on_garbage(self):
        out = _scenes.cluster_llm({"a.md": {"title": "x"}},
                                  llm_fn=lambda p: "not json at all", max_scenes=15)
        self.assertEqual(out, {})

    def test_survives_trailing_commentary_with_a_brace(self):
        """TASK-189: rfind('}') landed inside the commentary's brace, the
        slice failed to parse, and {} meant baseline recall, silently."""
        reply = ('{"scenes": [{"label": "s", "members": ["a.md"]}]}\n'
                 'Ik koos dit omdat {context} paste.')
        out = _scenes.cluster_llm({"a.md": {"title": "x"}},
                                  llm_fn=lambda p: reply, max_scenes=15)
        self.assertEqual(out, {"s": ["a.md"]})

    def test_a_brace_in_leading_prose_does_not_win(self):
        reply = ('Even {denken}. '
                 '{"scenes": [{"label": "s", "members": ["a.md"]}]}')
        out = _scenes.cluster_llm({"a.md": {"title": "x"}},
                                  llm_fn=lambda p: reply, max_scenes=15)
        self.assertEqual(out, {"s": ["a.md"]})

    def test_a_non_list_scenes_value_fails_open(self):
        out = _scenes.cluster_llm({"a.md": {"title": "x"}},
                                  llm_fn=lambda p: '{"scenes": "oops"}',
                                  max_scenes=15)
        self.assertEqual(out, {})

    def test_fails_open_when_the_model_raises(self):
        def boom(prompt):
            raise RuntimeError("model unreachable")

        out = _scenes.cluster_llm({"a.md": {"title": "x"}}, llm_fn=boom,
                                  max_scenes=15)
        self.assertEqual(out, {})

    def test_ignores_hallucinated_paths(self):
        out = _scenes.cluster_llm(
            {"a.md": {"title": "x"}},
            llm_fn=lambda p: '{"scenes":[{"label":"s","members":["a.md","ghost.md"]}]}',
            max_scenes=15)
        self.assertEqual(out, {"s": ["a.md"]})

    def test_a_path_claimed_twice_lands_in_one_scene(self):
        """Overlapping scenes would apply the prior twice for one query."""
        out = _scenes.cluster_llm(
            {"a.md": {"title": "x"}},
            llm_fn=lambda p: ('{"scenes":[{"label":"s1","members":["a.md"]},'
                              '{"label":"s2","members":["a.md"]}]}'),
            max_scenes=15)
        assigned = [p for v in out.values() for p in v]
        self.assertEqual(assigned, ["a.md"])

    def test_a_repeated_label_does_not_swallow_the_earlier_group(self):
        out = _scenes.cluster_llm(
            {"a.md": {"title": "x"}, "b.md": {"title": "y"}},
            llm_fn=lambda p: ('{"scenes":[{"label":"s","members":["a.md"]},'
                              '{"label":"s","members":["b.md"]}]}'),
            max_scenes=15)
        self.assertEqual(sorted(p for v in out.values() for p in v),
                         ["a.md", "b.md"])
        self.assertEqual(len(out), 2)


class SceneKnobsTest(unittest.TestCase):
    """The knobs must live in retrieve_params, or kb-eval drifts from the hook.

    kb-eval loads retrieve_params via importlib precisely so the harness
    measures the gate the hook applies. A knob resolved anywhere else would be
    invisible to the eval and silently unmeasured (the drift TASK-86 fixed).
    """

    def _retrieve(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "kb_retrieve_scenes", str(SCRIPTS / "kb-retrieve.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("KB_SCENE_FLOOR", "KB_SCENE_BOOST", "KB_SCENE_CLUSTERER")}
        for k in self._env:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_defaults_are_the_neutral_arm(self):
        p = self._retrieve().retrieve_params({})
        self.assertEqual(p["scene_floor"], 0.35)
        self.assertEqual(p["scene_boost"], 0.0)
        self.assertEqual(p["scene_clusterer"], "community")

    def test_env_overrides_win(self):
        os.environ["KB_SCENE_FLOOR"] = "0.4"
        os.environ["KB_SCENE_BOOST"] = "0.05"
        os.environ["KB_SCENE_CLUSTERER"] = "tags"
        p = self._retrieve().retrieve_params({})
        self.assertEqual(p["scene_floor"], 0.4)
        self.assertEqual(p["scene_boost"], 0.05)
        self.assertEqual(p["scene_clusterer"], "tags")

    def test_config_file_supplies_the_clusterer_without_env(self):
        p = self._retrieve().retrieve_params({"scene_clusterer": "llm"})
        self.assertEqual(p["scene_clusterer"], "llm")

    def test_toggle_defaults_off(self):
        import _settings
        self.assertIs(_settings.DEFAULTS["scene_retrieval"], False)


if __name__ == "__main__":
    unittest.main()
