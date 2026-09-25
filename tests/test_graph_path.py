from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _graph  # noqa: E402


class GraphPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-graph-path-"))
        self.vault = self.tmp / "vault"
        (self.vault / "graphify-out").mkdir(parents=True)
        self.graph_path = self.vault / "graphify-out" / "graph.json"
        self.graph = {
            "directed": False,
            "nodes": [
                {"id": "a1", "label": "A concept", "source_file": "02-wiki/a.md"},
                {"id": "a2", "label": "A second", "source_file": "02-wiki/a.md"},
                {"id": "mid", "label": "Bridge", "source_file": None},
                {"id": "b1", "label": "B concept", "source_file": "02-wiki/b.md"},
                {"id": "far", "label": "Far", "source_file": "02-wiki/c.md"},
            ],
            "links": [
                {"source": "a1", "target": "mid", "relation": "references", "confidence_score": 1},
                {"source": "a2", "target": "mid", "relation": "references", "confidence_score": 1},
                {"source": "mid", "target": "b1", "relation": "references", "confidence_score": 1},
                {"source": "a1", "target": "far", "relation": "references", "confidence_score": 1},
            ],
        }
        self._write_graph(self.graph)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_graph(self, graph):
        self.graph_path.write_text(json.dumps(graph), encoding="utf-8")

    def _query(self, source="02-wiki/a.md", target="02-wiki/b.md", **kwargs):
        return _graph.shortest_path(source, target, graph_path=self.graph_path,
                                    vault=self.vault, **kwargs)

    def test_connected_document_path_uses_all_nodes_and_returns_documents(self):
        result = self._query()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["hops"], 2)
        self.assertEqual([node["id"] for node in result["path"]], ["a1", "mid", "b1"])
        self.assertEqual(result["documents"], ["02-wiki/a.md", "02-wiki/b.md"])
        self.assertEqual(result["edges"][0]["relation"], "references")

    def test_disconnected_nodes_have_no_path(self):
        graph = dict(self.graph)
        graph["links"] = []
        self._write_graph(graph)
        result = self._query()
        self.assertEqual(result["status"], "no_path")
        self.assertEqual(result["path"], [])

    def test_self_path_has_zero_hops(self):
        result = self._query(source="a1", target="a1")
        self.assertEqual(result["status"], "self")
        self.assertEqual(result["hops"], 0)
        self.assertEqual([node["id"] for node in result["path"]], ["a1"])

    def test_edges_alias_is_accepted(self):
        graph = dict(self.graph)
        graph["edges"] = graph.pop("links")
        self._write_graph(graph)
        self.assertEqual(self._query()["status"], "ok")

    def test_directed_graph_is_not_traversed_backwards(self):
        graph = dict(self.graph)
        graph["directed"] = True
        graph["links"] = [
            {"source": "a1", "target": "mid", "relation": "references"},
            {"source": "mid", "target": "b1", "relation": "references"},
        ]
        self._write_graph(graph)
        result = self._query()
        self.assertEqual(result["status"], "ok")
        reverse = _graph.shortest_path(
            "02-wiki/b.md", "02-wiki/a.md", graph_path=self.graph_path,
            vault=self.vault)
        self.assertEqual(reverse["status"], "no_path")

    def test_equal_length_paths_are_deterministic_when_input_is_reordered(self):
        graph = dict(self.graph)
        graph["links"] = [
            {"source": "a1", "target": "mid", "relation": "z"},
            {"source": "a2", "target": "mid", "relation": "a"},
            {"source": "mid", "target": "b1", "relation": "r"},
            {"source": "a1", "target": "far", "relation": "r"},
        ]
        self._write_graph(graph)
        first = self._query()
        graph["links"] = list(reversed(graph["links"]))
        self._write_graph(graph)
        second = self._query()
        self.assertEqual(first, second)
        self.assertEqual(first["path"][0]["id"], "a1")

    def test_missing_graph_is_explicitly_unavailable(self):
        self.graph_path.unlink()
        result = self._query()
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("onleesbaar", result["reason"])


if __name__ == "__main__":
    unittest.main()
