"""Tests voor graph-scope-prune.py: alleen actuele memories blijven in de graaf.

De scope van de kennisgraaf komt uit `.graphifyignore` en dat werkt op paden.
De geheugenlaag heeft een scope-criterium dat niet in een pad zit: de
frontmatter-status. Deze tests leggen vast dat de na-stap precies dat
criterium toepast, de losgeraakte edges meeneemt, en van andere lagen afblijft.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script


def _memory(status: str) -> str:
    return f'---\ntitle: "m"\ntype: memory\nstatus: {status}\n---\n\ninhoud\n'


class GraphScopePruneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-prune-"))
        self.vault = self.tmp / "vault"
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "graphify-out").mkdir(parents=True)

        for name, status in (("cur", "current"), ("sup", "superseded"),
                             ("unv", "unverified"), ("exp", "expired")):
            (self.vault / "09-memory" / f"{name}.md").write_text(
                _memory(status), encoding="utf-8")
        (self.vault / "02-wiki" / "art.md").write_text("# art\n", encoding="utf-8")

        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.vault)
        self.mod = load_script("graph-scope-prune.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _graph(self) -> dict:
        return {
            "nodes": [
                {"id": 1, "source_file": "09-memory/cur.md"},
                {"id": 2, "source_file": "09-memory/sup.md"},
                {"id": 3, "source_file": "09-memory/unv.md"},
                {"id": 4, "source_file": "09-memory/exp.md"},
                {"id": 5, "source_file": "02-wiki/art.md"},
                {"id": 6, "source_file": "09-memory/weg.md"},
            ],
            "links": [
                {"source": 1, "target": 5},   # blijft: beide kanten overleven
                {"source": 2, "target": 5},   # weg: bron gesnoeid
                {"source": 5, "target": 4},   # weg: doel gesnoeid
            ],
        }

    def test_alleen_current_memories_blijven(self):
        graph, stats = self.mod.prune(self._graph(), self.vault)
        overgebleven = {n["source_file"] for n in graph["nodes"]}
        self.assertEqual(overgebleven, {"09-memory/cur.md", "02-wiki/art.md"})
        self.assertEqual(stats["nodes_pruned"], 4)

    def test_wiki_nodes_blijven_ongemoeid(self):
        graph, _ = self.mod.prune(self._graph(), self.vault)
        wiki = [n for n in graph["nodes"] if n["source_file"].startswith("02-wiki/")]
        self.assertEqual(len(wiki), 1)

    def test_losse_edges_verdwijnen_mee(self):
        graph, stats = self.mod.prune(self._graph(), self.vault)
        self.assertEqual(len(graph["links"]), 1)
        self.assertEqual(stats["links_pruned"], 2)
        ids = {n["id"] for n in graph["nodes"]}
        for link in graph["links"]:
            self.assertIn(link["source"], ids)
            self.assertIn(link["target"], ids)

    def test_verdwenen_bronbestand_wordt_gesnoeid_en_geteld(self):
        _, stats = self.mod.prune(self._graph(), self.vault)
        self.assertEqual(stats["files_missing"], 1)

    def test_idempotent(self):
        graph, _ = self.mod.prune(self._graph(), self.vault)
        graph2, stats2 = self.mod.prune(json.loads(json.dumps(graph)), self.vault)
        self.assertEqual(stats2["nodes_pruned"], 0)
        self.assertEqual(stats2["links_pruned"], 0)
        self.assertEqual(len(graph2["nodes"]), len(graph["nodes"]))

    def test_backslash_paden_worden_herkend(self):
        graph = {"nodes": [{"id": 1, "source_file": "09-memory\\sup.md"}], "links": []}
        _, stats = self.mod.prune(graph, self.vault)
        self.assertEqual(stats["nodes_pruned"], 1)


if __name__ == "__main__":
    unittest.main()
