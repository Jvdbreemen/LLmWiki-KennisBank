"""Tests voor de kennisgraaf in kb-index.db (TASK-71).

De kern van dit onderdeel is niet 'kan het de buren vinden' maar 'houdt het
zijn mond als het niet zeker weet'. Een verouderde graaf naast een verse
embedding-index mag GEEN buur opleveren; een verkeerde buur is erger dan geen
buur, want die verdringt een goede treffer.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402


def _graph():
    """Mini-graaf: twee documenten met eigen concepten, plus een doc-doc-edge.

    a.md heeft concepten a1/a2, b.md heeft b1. De contains-edges lopen van de
    documentnode naar de eigen concepten; die mogen NOOIT als buur tellen.
    """
    return {
        "nodes": [
            {"id": "doc:09-memory/a.md", "label": "A", "source_file": "09-memory/a.md",
             "file_type": "document", "community": 1},
            {"id": "mem_a1", "label": "A1", "source_file": "09-memory/a.md",
             "file_type": "concept", "community": 1},
            {"id": "mem_a2", "label": "A2", "source_file": "09-memory/a.md",
             "file_type": "concept", "community": 1},
            {"id": "doc:09-memory/b.md", "label": "B", "source_file": "09-memory/b.md",
             "file_type": "document", "community": 1},
            {"id": "mem_b1", "label": "B1", "source_file": "09-memory/b.md",
             "file_type": "concept", "community": 1},
            {"id": "doc:02-wiki/c.md", "label": "C", "source_file": "02-wiki/c.md",
             "file_type": "document", "community": 2},
        ],
        "links": [
            {"source": "doc:09-memory/a.md", "target": "mem_a1",
             "relation": "contains", "confidence_score": 1.0},
            {"source": "doc:09-memory/a.md", "target": "mem_a2",
             "relation": "contains", "confidence_score": 1.0},
            {"source": "doc:09-memory/b.md", "target": "mem_b1",
             "relation": "contains", "confidence_score": 1.0},
            {"source": "doc:09-memory/a.md", "target": "doc:09-memory/b.md",
             "relation": "same_session", "confidence_score": 1.0},
            {"source": "mem_a1", "target": "mem_b1",
             "relation": "semantically_similar_to", "confidence_score": 0.85},
            {"source": "mem_a2", "target": "doc:02-wiki/c.md",
             "relation": "references", "confidence_score": 0.5},
        ],
    }


class GraphIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-graphidx-"))
        self.db = self.tmp / "kb-index.db"
        self.graph = self.tmp / "graph.json"
        self.graph.write_text(json.dumps(_graph()), encoding="utf-8")
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        import _kbindex
        self.idx = _kbindex
        self.conn = _kbindex.graph_connect(self.db)
        g = _graph()
        _kbindex.replace_graph(self.conn, g["nodes"], g["links"])
        _kbindex.set_graph_fingerprint(self.conn, _kbindex.graph_fingerprint(self.graph))

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- structuur ---------------------------------------------------------

    def test_tabellen_en_indexen_bestaan(self):
        names = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index')").fetchall()}
        for expected in ("graph_nodes", "graph_edges", "idx_graph_nodes_src",
                         "idx_graph_edges_source", "idx_graph_edges_target"):
            self.assertIn(expected, names)

    def test_telling_klopt(self):
        n, e = self.idx.graph_count(self.conn)
        self.assertEqual((n, e), (6, 6))

    # --- buurquery ---------------------------------------------------------

    def test_buren_zijn_andere_bestanden(self):
        nb = self.idx.graph_neighbors(self.conn, "09-memory/a.md")
        paths = [x["source_file"] for x in nb]
        self.assertIn("09-memory/b.md", paths)
        self.assertNotIn("09-memory/a.md", paths)

    def test_het_bestand_zelf_is_nooit_zijn_eigen_buur(self):
        """Twee mechanismen dekken dit, en dat is bewust.

        De query sluit gelijke source_file uit; daarnaast vallen contains-edges
        weg via exclude_relations. Die tweede is verdedigingsdiepte: contains
        loopt per constructie binnen een bestand, dus de eerste filter vangt
        hem al. Zou graph-link-layer ooit een contains-edge over bestandsgrenzen
        leggen, dan houdt de tweede filter het gedrag hier gelijk.
        """
        for excl in ((), self.idx.GRAPH_SELF_RELATIONS):
            nb = self.idx.graph_neighbors(self.conn, "09-memory/a.md",
                                          exclude_relations=excl)
            self.assertNotIn("09-memory/a.md", [x["source_file"] for x in nb])

    def test_contains_edges_dragen_geen_gewicht(self):
        """a.md heeft twee contains-edges; die mogen het buurgewicht niet opblazen."""
        zonder = {x["source_file"]: x["weight"] for x in
                  self.idx.graph_neighbors(self.conn, "09-memory/a.md")}
        met = {x["source_file"]: x["weight"] for x in
               self.idx.graph_neighbors(self.conn, "09-memory/a.md", exclude_relations=())}
        self.assertEqual(zonder, met)

    def test_gewicht_telt_meerdere_verbindingen_op(self):
        """b.md hangt via twee edges aan a.md (1.0 + 0.85), c.md via een (0.5)."""
        nb = {x["source_file"]: x for x in self.idx.graph_neighbors(self.conn, "09-memory/a.md")}
        self.assertAlmostEqual(nb["09-memory/b.md"]["weight"], 1.85, places=6)
        self.assertEqual(nb["09-memory/b.md"]["hops"], 2)
        self.assertAlmostEqual(nb["02-wiki/c.md"]["weight"], 0.5, places=6)
        self.assertGreater(nb["09-memory/b.md"]["weight"], nb["02-wiki/c.md"]["weight"])

    def test_ongericht(self):
        """b.md moet a.md als buur zien, ook al staat a.md als source in de edge."""
        nb = [x["source_file"] for x in self.idx.graph_neighbors(self.conn, "09-memory/b.md")]
        self.assertIn("09-memory/a.md", nb)

    def test_drempel_filtert(self):
        nb = [x["source_file"] for x in
              self.idx.graph_neighbors(self.conn, "09-memory/a.md", min_confidence=0.8)]
        self.assertIn("09-memory/b.md", nb)
        self.assertNotIn("02-wiki/c.md", nb)  # die edge staat op 0.5

    def test_limiet(self):
        nb = self.idx.graph_neighbors(self.conn, "09-memory/a.md", limit=1)
        self.assertEqual(len(nb), 1)
        self.assertEqual(nb[0]["source_file"], "09-memory/b.md")  # zwaarste eerst

    def test_onbekend_bestand_geeft_niets(self):
        self.assertEqual(self.idx.graph_neighbors(self.conn, "09-memory/weg.md"), [])
        self.assertEqual(self.idx.graph_neighbors(self.conn, ""), [])

    # --- versheid ----------------------------------------------------------

    def test_verse_graaf_is_actueel(self):
        self.assertTrue(self.idx.graph_is_current(self.conn, self.graph))

    def test_gewijzigde_graaf_is_niet_meer_actueel(self):
        g = _graph()
        g["nodes"].append({"id": "nieuw", "source_file": "09-memory/z.md"})
        self.graph.write_text(json.dumps(g), encoding="utf-8")
        os.utime(self.graph, (0, 0))  # andere mtime EN andere grootte
        self.assertFalse(self.idx.graph_is_current(self.conn, self.graph))

    def test_ontbrekende_graaf_is_niet_actueel(self):
        self.graph.unlink()
        self.assertFalse(self.idx.graph_is_current(self.conn, self.graph))

    def test_versheid_staat_los_van_het_embedmodel(self):
        """De twee assen mogen elkaar niet beinvloeden.

        Deze test zette eerder BEIDE schema's op dezelfde verbinding om te tonen
        dat een modelwissel de graaf niet ongeldig maakt. Sinds TASK-75 kan dat
        niet meer -- en hoeft het niet meer: de graaf heeft een eigen bestand,
        dus de onafhankelijkheid is structureel in plaats van afgesproken. Wat
        overblijft is toetsen dat de graafversheid puur van graph.json afhangt en
        van geen enkele embedding-eigenschap.
        """
        self.assertTrue(self.idx.graph_is_current(self.conn, self.graph))
        # Een graafverbinding heeft geen embed-eigenschappen; is_valid_for hoort
        # daar fail-open op te reageren en niet te ontploffen.
        self.assertFalse(self.idx.is_valid_for(self.conn, "ollama:model-a"))
        self.assertTrue(self.idx.graph_is_current(self.conn, self.graph),
                        "graafversheid mag niet aan het embedmodel hangen")

    def test_graafindex_gebruikt_wal(self):
        """Vastgelegd omdat DELETE hier MEETBAAR sneller is (1,2 ms tegen 23,5 ms
        per verse lezer) en een latere snelheidsronde die keuze dus zou kunnen
        terugdraaien. De index kan meerdere agents tegelijk bedienen terwijl de
        worker hem herbouwt; WAL houdt lezers en schrijvers by design uit elkaar,
        DELETE leunt op de busy-timeout. Die 23 ms staan tegenover een
        sessiestart van ~1230 ms."""
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(str(mode).lower(), "wal")

    def test_lezers_worden_niet_geblokkeerd_door_een_herbouw(self):
        """De reden dat WAL hier staat: een lezer tijdens een lopende herbouw
        hoort gewoon antwoord te krijgen, niet SQLITE_BUSY."""
        import sqlite3 as _sq
        self.idx.replace_graph(
            self.conn,
            [{"id": "a", "source_file": "02-wiki/a.md"},
             {"id": "b", "source_file": "02-wiki/b.md"}],
            [{"source": "a", "target": "b", "relation": "references",
              "confidence_score": 1.0}])
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute("DELETE FROM graph_edges")
        try:
            lezer = _sq.connect(f"file:{self.db}?mode=ro", uri=True, timeout=0.5)
            try:
                n, _e = self.idx.graph_count(lezer)
                self.assertEqual(n, 2, "lezer ziet de vorige, consistente staat")
            finally:
                lezer.close()
        finally:
            self.conn.rollback()

    def test_graaf_heeft_een_eigen_bestand(self):
        """De kern van TASK-75: kb-index.db kan weggegooid worden, de graaf niet.

        Zie test_build_kb_index.test_een_volledige_herbouw_laat_de_graaf_intact
        voor het bewijs via de echte unlink-weg; hier alleen de padscheiding.
        """
        self.assertNotEqual(self.idx.graph_index_path(), self.idx.index_path())
        self.assertEqual(self.idx.graph_index_path().name, "kb-graph.db")

    def test_lege_index_geeft_geen_buur(self):
        """Fail-open: zonder graaftabellen geen exception, gewoon niets."""
        import _kbindex
        leeg = _kbindex.graph_connect(self.tmp / "leeg.db")
        try:
            self.assertEqual(_kbindex.graph_neighbors(leeg, "09-memory/a.md"), [])
            self.assertEqual(_kbindex.graph_count(leeg), (0, 0))
            self.assertFalse(_kbindex.graph_is_current(leeg, self.graph))
        finally:
            leeg.close()

    # --- vervangen ---------------------------------------------------------

    def test_replace_is_idempotent(self):
        g = _graph()
        voor = self.idx.graph_count(self.conn)
        self.idx.replace_graph(self.conn, g["nodes"], g["links"])
        self.assertEqual(self.idx.graph_count(self.conn), voor)

    def test_replace_verwijdert_oude_nodes(self):
        """Vervangen, niet samenvoegen: anders blijft een verdwenen node hangen."""
        self.idx.replace_graph(self.conn, [{"id": "enige", "source_file": "x.md"}], [])
        self.assertEqual(self.idx.graph_count(self.conn), (1, 0))
        self.assertEqual(self.idx.graph_neighbors(self.conn, "09-memory/a.md"), [])

    def test_nodes_zonder_id_worden_overgeslagen(self):
        n, _ = self.idx.replace_graph(self.conn, [{"source_file": "x.md"}, {"id": "ok"}], [])
        self.assertEqual(n, 1)

    def test_backslash_paden_worden_genormaliseerd(self):
        self.idx.replace_graph(
            self.conn,
            [{"id": "n1", "source_file": "09-memory\\win.md"},
             {"id": "n2", "source_file": "09-memory/other.md"}],
            [{"source": "n1", "target": "n2", "relation": "references",
              "confidence_score": 1.0}])
        nb = self.idx.graph_neighbors(self.conn, "09-memory/win.md")
        self.assertEqual([x["source_file"] for x in nb], ["09-memory/other.md"])


class BuilderTest(unittest.TestCase):
    """De builder zelf: laadt, slaat over bij ongewijzigd, en klaagt niet als
    graphify niet geinstalleerd is."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-graphbuild-"))
        self.db = self.tmp / "kb-index.db"
        self.graph = self.tmp / "graph.json"
        self.graph.write_text(json.dumps(_graph()), encoding="utf-8")
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mod = load_script("build-graph-index.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv):
        import io
        saved_argv, saved_out = sys.argv, sys.stdout
        buf = io.StringIO()
        sys.argv = ["build-graph-index.py", "--graph", str(self.graph),
                    "--db", str(self.db), "--json", *argv]
        sys.stdout = buf
        try:
            code = self.mod.main()
        finally:
            sys.argv, sys.stdout = saved_argv, saved_out
        return code, json.loads(buf.getvalue() or "{}")

    def test_eerste_run_laadt(self):
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "geladen")
        self.assertEqual((out["nodes"], out["edges"]), (6, 6))

    def test_tweede_run_slaat_over(self):
        self._run()
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "ongewijzigd")

    def test_force_herlaadt_toch(self):
        self._run()
        code, out = self._run("--force")
        self.assertEqual(out["status"], "geladen")

    def test_ontbrekende_graaf_is_geen_fout(self):
        """graphify is een externe skill; niet-geinstalleerd is een geldige staat."""
        self.graph.unlink()
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "geen-graaf")

    def test_kapotte_graaf_geeft_exitcode_1(self):
        self.graph.write_text("{dit is geen json", encoding="utf-8")
        code, _out = self._run()
        self.assertEqual(code, 1)

    def test_edges_sleutel_wordt_ook_geaccepteerd(self):
        g = _graph()
        g["edges"] = g.pop("links")
        self.graph.write_text(json.dumps(g), encoding="utf-8")
        _code, out = self._run()
        self.assertEqual(out["edges"], 6)


if __name__ == "__main__":
    unittest.main()
