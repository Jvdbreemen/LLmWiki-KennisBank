"""Tests voor de provenance-ring (TASK-68).

De kern van dit onderdeel is niet "vindt hij de sessies" maar "blijft een sessie
een BLAD". Provenance-nodes horen herkomst te dragen, geen kennis; zodra ze als
gewone buur meetellen, verdringen ze de artikelen waar het antwoord in staat.
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
from _loader import load_script  # noqa: E402


class ProvenanceRingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-prov-"))
        (self.tmp / "01-raw" / "sessies").mkdir(parents=True)
        (self.tmp / "02-wiki").mkdir(parents=True)
        (self.tmp / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mod = load_script("graph-provenance-ring.py")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _sessie(self, stem, transcript="s1.jsonl", type_="raw-sessie", datum="2026-07-01"):
        pad = self.tmp / "01-raw" / "sessies" / f"{stem}.md"
        sp = (f"source_path: D:\\Users\\x\\transcripts\\{transcript}\n"
              if transcript else "")
        pad.write_text(f"---\ntitle: \"Sessie {stem}\"\ntype: {type_}\n{sp}"
                       f"date: {datum}\n---\n\nlogtekst", encoding="utf-8")
        return f"01-raw/sessies/{stem}.md"

    def _memory(self, naam, source_session="", body="inhoud"):
        pad = self.tmp / "09-memory" / f"{naam}.md"
        ss = f'source_session: "{source_session}"\n' if source_session else ""
        pad.write_text(f"---\ntitle: {naam}\ntype: memory\nstatus: current\n{ss}---\n\n{body}",
                       encoding="utf-8")
        return f"09-memory/{naam}.md"

    def _wiki(self, naam, body="tekst"):
        (self.tmp / "02-wiki" / f"{naam}.md").write_text(
            f"---\ntitle: {naam}\ntype: wiki\n---\n\n{body}", encoding="utf-8")
        return f"02-wiki/{naam}.md"

    def _graaf(self, bronnen):
        return {"nodes": [{"id": f"c{i}", "label": f"C{i}", "source_file": rel,
                           "file_type": "concept", "community": 1}
                          for i, rel in enumerate(bronnen)],
                "links": []}

    def _bouw(self, graaf):
        sessies = self.mod.read_sessions(self.tmp)
        docs = self.mod.read_referrers(graaf, self.tmp)
        return self.mod.build_ring(graaf, sessies, docs)

    # --- nodes --------------------------------------------------------------

    def test_verwezen_sessie_krijgt_een_node_zonder_llm(self):
        self._sessie("raw-sessie-a", transcript="s1.jsonl")
        self._sessie("raw-sessie-b", transcript="s2.jsonl")
        rels = [self._memory("m1", source_session="s1.jsonl"),
                self._memory("m2", source_session="s2.jsonl")]
        nodes, _e, rap = self._bouw(self._graaf(rels))
        self.assertEqual(len(nodes), 2)
        self.assertEqual(rap["sessies"], 2)

    def test_sessie_zonder_verwijzing_krijgt_standaard_geen_node(self):
        """Een blad zonder tak is geen ring maar ruis. Gemeten op een echte
        vault: 724 van de 772 sessies zou zo als losse node landen, en dat maakt
        de isolatie-winst van graph-link-layer (437 -> 2) in een klap ongedaan."""
        self._sessie("raw-sessie-los", transcript="niemand.jsonl")
        nodes, edges, rap = self._bouw(self._graaf([]))
        self.assertEqual(nodes, [])
        self.assertEqual(edges, [])
        self.assertEqual(rap["sessies_zonder_enige_verwijzing"], 1)

    def test_include_unreferenced_neemt_ze_wel_op(self):
        self._sessie("raw-sessie-los", transcript="niemand.jsonl")
        graaf = self._graaf([])
        sessies = self.mod.read_sessions(self.tmp)
        docs = self.mod.read_referrers(graaf, self.tmp)
        nodes, _e, _r = self.mod.build_ring(graaf, sessies, docs,
                                            include_unreferenced=True)
        self.assertEqual(len(nodes), 1)

    def test_nodes_zijn_herkenbaar_als_provenance(self):
        """AC #3: ranking moet ze kunnen onderscheiden van kennis-nodes."""
        self._sessie("raw-sessie-a", transcript="s1.jsonl")
        rel = self._memory("m1", source_session="s1.jsonl")
        nodes, _e, _r = self._bouw(self._graaf([rel]))
        self.assertEqual(nodes[0]["file_type"], self.mod.PROV_FILE_TYPE)
        self.assertTrue(nodes[0]["id"].startswith(self.mod.PROV_PREFIX))

    def test_bestanden_zonder_raw_sessie_type_tellen_niet_mee(self):
        self._sessie("gewoon-bestand", type_="wiki")
        nodes, _e, rap = self._bouw(self._graaf([]))
        self.assertEqual(nodes, [])
        self.assertEqual(rap["sessies"], 0)

    # --- edges --------------------------------------------------------------

    def test_edge_via_source_session(self):
        self._sessie("raw-sessie-a", transcript="2026-07-01-project-abc123.jsonl")
        rel = self._memory("m1", source_session="2026-07-01-project-abc123.jsonl")
        _n, edges, rap = self._bouw(self._graaf([rel]))
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["relation"], "captured_in")
        self.assertEqual(edges[0]["source"], "doc:09-memory/m1.md")
        self.assertEqual(edges[0]["target"], "sessie:01-raw/sessies/raw-sessie-a.md")
        self.assertEqual(rap["edges_via_source_session"], 1)

    def test_edge_via_wikilink(self):
        self._sessie("raw-sessie-a")
        rel = self._wiki("artikel", body="zie [[raw-sessie-a]] voor de herkomst")
        _n, edges, rap = self._bouw(self._graaf([rel]))
        self.assertEqual(len(edges), 1)
        self.assertEqual(rap["edges_via_wikilink"], 1)

    def test_windows_pad_in_source_path_wordt_herkend(self):
        """source_path staat zoals de importeur hem zag: met backslashes. Op een
        POSIX-machine ziet Path die niet als scheidingsteken."""
        self._sessie("raw-sessie-a", transcript="t.jsonl")
        rel = self._memory("m1", source_session="t.jsonl")
        _n, edges, _r = self._bouw(self._graaf([rel]))
        self.assertEqual(len(edges), 1)

    def test_geen_edges_tussen_sessies_onderling(self):
        """Blad, geen knooppunt: een tweede hub-structuur naast same_session
        zou hetzelfde te grove signaal opleveren."""
        self._sessie("raw-sessie-a", transcript="s1.jsonl")
        self._sessie("raw-sessie-b", transcript="s2.jsonl")
        _n, edges, _r = self._bouw(self._graaf([]))
        self.assertEqual(edges, [])

    def test_onbekende_source_session_levert_geen_edge(self):
        self._sessie("raw-sessie-a", transcript="s1.jsonl")
        rel = self._memory("m1", source_session="bestaat-niet.jsonl")
        _n, edges, _r = self._bouw(self._graaf([rel]))
        self.assertEqual(edges, [])

    # --- rapportage ---------------------------------------------------------

    def test_niet_matchende_sessies_worden_geteld_niet_verzwegen(self):
        """AC #2: stil weglaten maakt een gat onzichtbaar."""
        self._sessie("raw-sessie-los", transcript="niemand.jsonl")
        self._sessie("raw-sessie-zonder-pad", transcript="")
        rel = self._memory("m1", source_session="niemand-anders.jsonl")
        _n, _e, rap = self._bouw(self._graaf([rel]))
        self.assertEqual(rap["sessies_zonder_enige_verwijzing"], 2)
        self.assertEqual(rap["sessies_zonder_source_path"], 1)
        self.assertTrue(rap["voorbeeld_ongekoppeld"], "voorbeelden maken het onderzoekbaar")

    # --- idempotentie -------------------------------------------------------

    def test_tweede_run_voegt_niets_toe(self):
        self._sessie("raw-sessie-a", transcript="s1.jsonl")
        rel = self._memory("m1", source_session="s1.jsonl")
        graaf = self._graaf([rel])
        nodes, edges, _r = self._bouw(graaf)
        graaf["nodes"].extend(nodes)
        graaf["links"].extend(edges)
        nodes2, edges2, _r2 = self._bouw(graaf)
        self.assertEqual(nodes2, [])
        self.assertEqual(edges2, [])

    # --- ADR-0002 -----------------------------------------------------------

    def test_geen_hardcoded_vaultpad(self):
        bron = (Path(__file__).resolve().parent.parent
                / "scripts" / "graph-provenance-ring.py").read_text(encoding="utf-8")
        self.assertIn("from _vaultpath import vault_root", bron)
        self.assertNotIn('Path.home() / "KennisBank"', bron)


class RankIsolatieTest(unittest.TestCase):
    """AC #4: provenance mag nooit boven een directe treffer uitkomen.

    Dat is hier geen weging maar een structurele eigenschap, en die is het
    waard om vast te leggen: one_hop_neighbor accepteert alleen targets die als
    artikel in 02-wiki/ bestaan. Een sessie in 01-raw kan er per constructie
    niet uitkomen. Zou iemand die filter ooit verruimen, dan valt deze test om.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rank-prov-"))
        (self.tmp / "02-wiki").mkdir(parents=True)
        (self.tmp / "01-raw" / "sessies").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_one_hop_neighbor_geeft_nooit_een_sessie_terug(self):
        rank = load_script("_rank.py") if (Path(__file__).resolve().parent.parent
                                           / "scripts" / "_rank.py").exists() else None
        self.assertIsNotNone(rank, "_rank.py hoort te bestaan")
        artikel = self.tmp / "02-wiki" / "artikel.md"
        artikel.write_text("zie [[raw-sessie-a]] en [[ander-artikel]]", encoding="utf-8")
        (self.tmp / "02-wiki" / "ander-artikel.md").write_text("x", encoding="utf-8")
        (self.tmp / "01-raw" / "sessies" / "raw-sessie-a.md").write_text("x", encoding="utf-8")
        buur = rank.one_hop_neighbor(
            [{"path": str(artikel), "layer": "wiki"}], self.tmp)
        self.assertNotEqual(buur, "raw-sessie-a")
        self.assertEqual(buur, "ander-artikel",
                         "alleen een bestaand wiki-artikel mag als buur terugkomen")


if __name__ == "__main__":
    unittest.main()
