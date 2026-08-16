"""Tests voor de graafbuur op de retrieval-leesweg (TASK-87, Spoor B).

Fixture-graaf via _kbindex.graph_connect + replace_graph + set_graph_fingerprint;
geen model, geen embedding-index. De harde eisen:

- toggle aan  -> buur uit kb-graph.db, gewogen, wiki-only, nooit een hit-stem;
- toggle uit  -> geen buur (TASK-93: de legacy one_hop_neighbor-terugval is
                 verwijderd nadat vier releases met de graaf-default AAN geen
                 regressie meldden; uit is nu puur een schakelaar, geen
                 source-select meer);
- fail-open   -> stale vingerafdruk, ontbrekende db of ontbrekende bestanden
                 geven GEEN buur en NOOIT een exceptie.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._loader import SCRIPTS_DIR, load_script


def _load_recall():
    return load_script("kb-recall.py")


class GraphNeighborTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        (self.vault / "graphify-out").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        self.kb = _load_recall()
        self.kbindex = self.kb._kbindex

        for stem in ("hit-artikel", "zware-buur", "lichte-buur"):
            (self.vault / "02-wiki" / f"{stem}.md").write_text(
                f"---\ntitle: {stem}\n---\n\nInhoud {stem}.\n", encoding="utf-8")

        # graph.json (alleen voor de vingerafdruk) + kb-graph.db
        self.graph_json = self.vault / "graphify-out" / "graph.json"
        self.graph_json.write_text("{}", encoding="utf-8")

    def _build_graph(self, nodes, edges, fresh=True):
        conn = self.kbindex.graph_connect()
        self.kbindex.replace_graph(conn, nodes, edges)
        fp = self.kbindex.graph_fingerprint(self.graph_json) if fresh else "0:0"
        self.kbindex.set_graph_fingerprint(conn, fp)
        conn.close()

    def _default_graph(self, fresh=True):
        """hit-artikel grenst aan zware-buur (2 edges, conf 1.0) en lichte-buur
        (1 edge, conf 0.65 shares_tag) + een contains-edge die niet mag tellen."""
        nodes = [
            {"id": "n-hit", "label": "hit", "source_file": "02-wiki/hit-artikel.md"},
            {"id": "n-zwaar", "label": "zwaar", "source_file": "02-wiki/zware-buur.md"},
            {"id": "n-licht", "label": "licht", "source_file": "02-wiki/lichte-buur.md"},
            {"id": "n-mem", "label": "mem", "source_file": "09-memory/x.md"},
        ]
        edges = [
            {"source": "n-hit", "target": "n-zwaar", "relation": "references",
             "confidence_score": 1.0},
            {"source": "n-zwaar", "target": "n-hit", "relation": "same_session",
             "confidence_score": 1.0},
            {"source": "n-hit", "target": "n-licht", "relation": "shares_tag",
             "confidence_score": 0.65},
            {"source": "n-hit", "target": "n-mem", "relation": "references",
             "confidence_score": 1.0},
            {"source": "n-hit", "target": "n-hit", "relation": "contains",
             "confidence_score": 1.0},
        ]
        self._build_graph(nodes, edges, fresh=fresh)

    def _hits(self):
        return [{"path": str(self.vault / "02-wiki" / "hit-artikel.md"),
                 "layer": "wiki", "score": 0.8}]

    # --- graph_neighbor zelf ---

    def test_weighted_neighbor_wins(self):
        self._default_graph()
        nb = self.kb.graph_neighbor(self._hits())
        self.assertIsNotNone(nb)
        self.assertEqual(nb["stem"], "zware-buur")

    def test_contains_excluded_and_memory_never_neighbor(self):
        nodes = [
            {"id": "n-hit", "label": "hit", "source_file": "02-wiki/hit-artikel.md"},
            {"id": "n-mem", "label": "mem", "source_file": "09-memory/x.md"},
        ]
        edges = [
            {"source": "n-hit", "target": "n-mem", "relation": "references",
             "confidence_score": 1.0},
            {"source": "n-hit", "target": "n-hit", "relation": "contains",
             "confidence_score": 1.0},
        ]
        self._build_graph(nodes, edges)
        self.assertIsNone(self.kb.graph_neighbor(self._hits()))

    def test_stale_fingerprint_gives_no_neighbor(self):
        self._default_graph(fresh=False)
        self.assertIsNone(self.kb.graph_neighbor(self._hits()))

    def test_missing_db_gives_no_neighbor_no_exception(self):
        # geen graph db gebouwd
        self.assertIsNone(self.kb.graph_neighbor(self._hits()))

    def test_missing_neighbor_file_falls_through_deterministically(self):
        self._default_graph()
        (self.vault / "02-wiki" / "zware-buur.md").unlink()
        nb = self.kb.graph_neighbor(self._hits())
        self.assertIsNotNone(nb)
        self.assertEqual(nb["stem"], "lichte-buur")

    def test_hit_stem_never_returned_as_neighbor(self):
        self._default_graph()
        hits = self._hits() + [{"path": str(self.vault / "02-wiki" / "zware-buur.md"),
                                "layer": "wiki", "score": 0.7}]
        nb = self.kb.graph_neighbor(hits)
        self.assertIsNotNone(nb)
        self.assertEqual(nb["stem"], "lichte-buur")

    # --- toggle-branch (_neighbor_entry) ---

    def test_toggle_off_yields_no_entry(self):
        """TASK-93: uit betekent geen buur, geen terugval meer op een
        tweede implementatie."""
        self._default_graph()
        import _settings
        with patch.object(_settings, "get",
                          side_effect=lambda k, d: False if k == "graph_retrieval" else d):
            entry = self.kb._neighbor_entry(self._hits())
        self.assertIsNone(entry)

    def test_toggle_on_uses_graph_path(self):
        self._default_graph()
        import _settings
        with patch.object(_settings, "get",
                          side_effect=lambda k, d: True if k == "graph_retrieval" else d):
            entry = self.kb._neighbor_entry(self._hits())
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "zware-buur")
        self.assertTrue(entry["neighbor"])

    def test_settings_get_raising_keeps_default_on(self):
        """TASK-188: _settings onleesbaar is niet 'feature uit'. get() is
        zelf al fail-open, dus een crash daar mag de default-ON buur niet
        stil uitschakelen."""
        self._default_graph()
        import _settings
        with patch.object(_settings, "get", side_effect=RuntimeError):
            entry = self.kb._neighbor_entry(self._hits())
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "zware-buur")

    def test_toggle_on_stale_graph_yields_no_entry(self):
        self._default_graph(fresh=False)
        import _settings
        with patch.object(_settings, "get",
                          side_effect=lambda k, d: True if k == "graph_retrieval" else d):
            entry = self.kb._neighbor_entry(self._hits())
        self.assertIsNone(entry)


class NeighborTelemetryTest(unittest.TestCase):
    """neighbor_log: de stil-leeg-guard voor de expansie (TASK-15-les)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        vault = Path(self.tmp.name) / "vault"
        (vault / ".claude").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import importlib
        import _usage
        importlib.reload(_usage)
        self.usage = _usage

    def test_neighbor_stems_counted(self):
        n = self.usage.log_injected(["a", "b"], neighbor_stems=["b"])
        self.assertEqual(n, 2)
        self.assertEqual(self.usage.neighbor_injected(30), 1)

    def test_no_neighbors_counts_zero(self):
        self.usage.log_injected(["a"])
        self.assertEqual(self.usage.neighbor_injected(30), 0)

    def test_neighbor_stem_must_be_injected_too(self):
        # een buur-stem die niet in stems zit telt niet mee (consistentie-guard)
        self.usage.log_injected(["a"], neighbor_stems=["ghost"])
        self.assertEqual(self.usage.neighbor_injected(30), 0)


if __name__ == "__main__":
    unittest.main()
