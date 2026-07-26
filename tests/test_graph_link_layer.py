"""Tests voor graph-link-layer.py: deterministische edges over de kennisgraaf.

De laag moet doen wat LLM-extractie per chunk niet kan: concepten aan hun
document hangen en documenten onderling verbinden via structuur die al in de
vault ligt. Deze tests leggen de garanties vast waarop de rest steunt -
ster-in-plaats-van-kliek, zeldzame tags, en idempotentie.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


def _doc(title: str, session: str = "", tags: str = "", body: str = "tekst") -> str:
    fm = [f'title: "{title}"', "type: memory", "status: current"]
    if session:
        fm.append(f'source_session: "{session}"')
    if tags:
        fm.append(f"tags: [{tags}]")
    return "---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n"


class GraphLinkLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-linklayer-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / "02-wiki").mkdir(parents=True)

        (self.vault / "09-memory" / "a.md").write_text(
            _doc("A", session="s1", tags="alpha", body="zie [[artikel]]"), encoding="utf-8")
        (self.vault / "09-memory" / "b.md").write_text(
            _doc("B", session="s1", tags="alpha"), encoding="utf-8")
        (self.vault / "09-memory" / "c.md").write_text(
            _doc("C", session="s2"), encoding="utf-8")
        (self.vault / "02-wiki" / "artikel.md").write_text(
            _doc("Artikel"), encoding="utf-8")

        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = load_script("graph-link-layer.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _graph(self) -> dict:
        return {
            "nodes": [
                {"id": "memory_a_x", "source_file": "09-memory/a.md"},
                {"id": "memory_a_y", "source_file": "09-memory/a.md"},
                {"id": "memory_b_x", "source_file": "09-memory/b.md"},
                {"id": "memory_c_x", "source_file": "09-memory/c.md"},
                {"id": "wiki_artikel_x", "source_file": "02-wiki/artikel.md"},
            ],
            "links": [],
        }

    def _apply(self, graph=None):
        graph = graph if graph is not None else self._graph()
        docs = self.mod.read_documents(graph, self.vault)
        nodes, edges, stats = self.mod.build_layer(graph, docs)
        return graph, nodes, edges, stats

    def test_elk_concept_hangt_aan_zijn_document(self):
        _, nodes, edges, stats = self._apply()
        self.assertEqual(stats["contains"], 5)
        contained = {e["target"] for e in edges if e["relation"] == "contains"}
        self.assertEqual(contained, {"memory_a_x", "memory_a_y", "memory_b_x",
                                     "memory_c_x", "wiki_artikel_x"})
        self.assertEqual(len(nodes), 4)  # een documentnode per bronbestand

    def test_same_session_verbindt_alleen_binnen_de_sessie(self):
        _, _, edges, _ = self._apply()
        sess = [(e["source"], e["target"]) for e in edges if e["relation"] == "same_session"]
        self.assertEqual(sess, [("doc:09-memory/a.md", "doc:09-memory/b.md")])

    def test_wikilink_wordt_een_references_edge(self):
        _, _, edges, _ = self._apply()
        refs = [(e["source"], e["target"]) for e in edges if e["relation"] == "references"]
        self.assertIn(("doc:09-memory/a.md", "doc:02-wiki/artikel.md"), refs)

    def test_ster_in_plaats_van_kliek(self):
        # Vijf documenten uit een sessie geven 4 edges, geen 10.
        for name in "defgh":
            (self.vault / "09-memory" / f"{name}.md").write_text(
                _doc(name.upper(), session="s3"), encoding="utf-8")
        graph = self._graph()
        graph["nodes"].extend({"id": f"memory_{n}_x", "source_file": f"09-memory/{n}.md"}
                              for n in "defgh")
        _, _, edges, _ = self._apply(graph)
        s3 = [e for e in edges if e["relation"] == "same_session"
              and "doc:09-memory/d.md" in (e["source"], e["target"])]
        self.assertEqual(len(s3), 4)

    def test_brede_tag_levert_geen_edges(self):
        names = [f"t{i}" for i in range(self.mod.TAG_MAX_DOCS + 2)]
        for name in names:
            (self.vault / "09-memory" / f"{name}.md").write_text(
                _doc(name, tags="breed"), encoding="utf-8")
        graph = {"nodes": [{"id": f"memory_{n}_x", "source_file": f"09-memory/{n}.md"}
                           for n in names], "links": []}
        _, _, edges, stats = self._apply(graph)
        self.assertEqual([e for e in edges if e["relation"] == "shares_tag"], [])
        self.assertEqual(stats.get("tags_te_breed"), 1)

    def test_idempotent(self):
        graph, nodes, edges, _ = self._apply()
        graph["nodes"].extend(nodes)
        graph["links"].extend(edges)
        docs = self.mod.read_documents(graph, self.vault)
        nodes2, edges2, _ = self.mod.build_layer(graph, docs)
        self.assertEqual(nodes2, [])
        self.assertEqual(edges2, [])

    def test_ontbrekend_bronbestand_wordt_overgeslagen(self):
        graph = self._graph()
        graph["nodes"].append({"id": "weg_x", "source_file": "09-memory/weg.md"})
        _, nodes, _, _ = self._apply(graph)
        self.assertNotIn("doc:09-memory/weg.md", {n["id"] for n in nodes})

    def test_geen_self_edge(self):
        _, _, edges, _ = self._apply()
        for e in edges:
            self.assertNotEqual(e["source"], e["target"])


if __name__ == "__main__":
    unittest.main()
