from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _kbindex  # noqa: E402

DIM = 4


class KbIndexSearchTest(unittest.TestCase):
    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")
        # twee dichtbij, één ver weg
        _kbindex.upsert(self.conn, path="near.md", layer="memory", status="current",
                        body="hook gedreven retrieval bug", vector=[0.10, 0.20, 0.30, 0.40],
                        file_hash="h1", created="2026-06-01")
        _kbindex.upsert(self.conn, path="far.md", layer="wiki", status="current",
                        body="sqlite vector index", vector=[0.90, 0.80, 0.70, 0.60],
                        file_hash="h2", created="2026-06-02")
        _kbindex.upsert(self.conn, path="hidden.md", layer="memory", status="unverified",
                        body="hook geheim", vector=[0.11, 0.21, 0.31, 0.41],
                        file_hash="h3", created="2026-06-03")

    def tearDown(self):
        self.conn.close()

    def test_vector_only_orders_by_proximity(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5)
        paths = [r["path"] for r in res]
        self.assertEqual(paths[0], "near.md")  # exact match bovenaan
        self.assertIn("far.md", paths)

    def test_status_filter_excludes_unverified(self):
        res = _kbindex.search(self.conn, query_vector=[0.11, 0.21, 0.31, 0.41], k=5,
                              statuses=("current",))
        self.assertNotIn("hidden.md", [r["path"] for r in res])

    def test_layer_filter(self):
        res = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5,
                              layers=("wiki",))
        self.assertEqual([r["path"] for r in res], ["far.md"])

    def test_hybrid_uses_keyword(self):
        # vector wijst naar far, maar keyword 'bug' staat alleen in near
        res = _kbindex.search(self.conn, query_vector=[0.90, 0.80, 0.70, 0.60],
                              query_text="bug", k=5)
        self.assertIn("near.md", [r["path"] for r in res])

    def test_statuses_none_returns_unverified(self):
        """statuses=None mag onverifieerde docs doorlaten."""
        res = _kbindex.search(self.conn, query_vector=[0.11, 0.21, 0.31, 0.41], k=5,
                              statuses=None)
        paths = [r["path"] for r in res]
        self.assertIn("hidden.md", paths, "statuses=None moet ook unverified docs retourneren")

    def test_result_count_bounded_by_k(self):
        """len(result) mag k nooit overschrijden."""
        res = _kbindex.search(self.conn, query_vector=[0.50, 0.50, 0.50, 0.50], k=2)
        self.assertLessEqual(len(res), 2)


class LayerStarvationRegressionTest(unittest.TestCase):
    """Regression: memory doc mag niet uit de pool vallen door wiki-concurrenten.

    Scenario: 25 wiki docs liggen dichter bij de probe-vector dan 1 memory doc.
    Oud gedrag (pool=max(k*4,20)=20): top-20 zijn allemaal wiki; memory doc
    heeft rank 26 en valt eraf vóór de layer-filter → zoekresultaat leeg.
    Nieuw gedrag (pool dekt het gehele corpus): alle 26 docs in pool → memory
    doc overleeft de layer-filter.
    """

    def test_memory_doc_not_starved_by_wiki_docs(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")

        probe = [1.0, 0.0, 0.0, 0.0]
        # 25 wiki-vectors dicht bij probe (L2-afstand 0.005..0.125 van probe)
        for i in range(25):
            _kbindex.upsert(conn,
                path=f"wiki_{i:02d}.md", layer="wiki", status="current",
                body=f"wiki doc {i}",
                vector=[1.0 - (i + 1) * 0.005, 0.0, 0.0, 0.0],
                file_hash=f"hw{i}", created="2026-06-27")
        # 1 memory-vector veraf (L2-afstand ≈ 1.414), dus rank 26 van 26
        _kbindex.upsert(conn,
            path="mem_key.md", layer="memory", status="current",
            body="memory key doc",
            vector=[0.0, 0.0, 0.0, 1.0],
            file_hash="hmem", created="2026-06-27")

        res = _kbindex.search(conn, query_vector=probe, layers=("memory",), k=5)
        conn.close()
        paths = [r["path"] for r in res]
        self.assertIn(
            "mem_key.md", paths,
            "memory doc was starved out of the candidate pool by closer wiki docs "
            "(pool te klein — pool-fix ontbreekt?)")


class RelevanceFloorTest(unittest.TestCase):
    """De hot path injecteerde onvoorwaardelijk de top-k.

    RRF-scores zijn rangnummer-artefacten en zeggen niets over inhoudelijke
    gelijkenis, dus de drempel hoort op de cosinus te liggen. Die komt gratis
    uit de L2-afstand die de KNN al teruggeeft, mits genormaliseerd opgeslagen.

    Fixture met TEGENGESTELDE vectoren: de bestaande near/far-fixture heeft
    cosinus 0.84 en zou elke drempel onder 0.84 overleven -- een test die ook
    zonder de fix slaagt toetst niets.
    """

    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")
        _kbindex.set_unit_norm(self.conn, True)
        _kbindex.upsert(self.conn, path="aligned.md", layer="wiki", status="current",
                        body="zebrafish morphology", vector=[1.0, 0.0, 0.0, 0.0],
                        file_hash="h1", created="2026-07-01")
        _kbindex.upsert(self.conn, path="orthogonal.md", layer="wiki", status="current",
                        body="quilting patterns", vector=[0.0, 0.0, 0.0, 1.0],
                        file_hash="h2", created="2026-07-02")

    def tearDown(self):
        self.conn.close()

    def test_cosine_is_reported_per_hit(self):
        res = _kbindex.search(self.conn, query_vector=[1.0, 0.0, 0.0, 0.0], k=5)
        by_path = {r["path"]: r for r in res}
        self.assertAlmostEqual(by_path["aligned.md"]["cos"], 1.0, places=5)
        self.assertAlmostEqual(by_path["orthogonal.md"]["cos"], 0.0, places=5)

    def test_floor_drops_the_irrelevant_hit(self):
        res = _kbindex.search(self.conn, query_vector=[1.0, 0.0, 0.0, 0.0],
                              k=5, min_cos=0.60)
        self.assertEqual([r["path"] for r in res], ["aligned.md"],
                         "een orthogonaal document overleefde de relevantiedrempel")

    def test_no_floor_without_the_unit_norm_flag(self):
        """Index van vóór de normalisatie: gedrag moet ongewijzigd blijven."""
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")
        for path, vec in (("a.md", [1.0, 0.0, 0.0, 0.0]), ("b.md", [0.0, 0.0, 0.0, 1.0])):
            _kbindex.upsert(conn, path=path, layer="wiki", status="current",
                            body="tekst", vector=vec, file_hash=path, created="2026-07-01")
        res = _kbindex.search(conn, query_vector=[1.0, 0.0, 0.0, 0.0], k=5, min_cos=0.60)
        conn.close()
        self.assertEqual(len(res), 2, "zonder unit_norm-vlag mag er niet gedrempeld worden")

    def test_fts_hit_survives_the_floor(self):
        """Een letterlijke trefwoordtreffer is een eigenstandig signaal."""
        res = _kbindex.search(self.conn, query_vector=[1.0, 0.0, 0.0, 0.0],
                              query_text="quilting patterns", k=5, min_cos=0.60)
        self.assertIn("orthogonal.md", [r["path"] for r in res])
        hit = next(r for r in res if r["path"] == "orthogonal.md")
        self.assertTrue(hit["fts"])

    def test_filter_runs_before_the_k_cut(self):
        """Bij k=1 mag een afgewezen treffer geen plek innemen."""
        res = _kbindex.search(self.conn, query_vector=[0.0, 0.0, 0.0, 1.0],
                              k=1, min_cos=0.60)
        self.assertEqual([r["path"] for r in res], ["orthogonal.md"])

    def test_punctuation_in_the_query_does_not_kill_the_fts_half(self):
        """De rauwe prompt gooide op `?`, `/` en `+`; dat werd stil ingeslikt."""
        expr = _kbindex.fts_expr("hoe werkt /wiki + de hook?")
        self.assertNotIn("/", expr)
        self.assertNotIn("?", expr)
        res = _kbindex.search(self.conn, query_vector=[1.0, 0.0, 0.0, 0.0],
                              query_text="quilting? / patterns +", k=5)
        self.assertTrue(any(r["fts"] for r in res),
                        "FTS-helft viel weg op een prompt met leestekens")


class Vec0PoolCeilingTest(unittest.TestCase):
    """sqlite-vec weigert een KNN met k > 4096 ("k value in knn query too large").

    De pool schaalt mee met het aantal docs, dus een groeiende vault liep die
    limiet vanzelf voorbij. De OperationalError viel buiten de FTS-try in
    search(), propageerde naar kb-recall en zette recall stil op [].
    """

    def test_pool_ceiling_matches_vec0_limit(self):
        self.assertEqual(_kbindex.VEC0_MAX_K, 4096)

    def test_search_survives_a_corpus_above_the_vec0_limit(self):
        conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(conn, dim=DIM, embed_id="ollama:test")
        # 4097 docs -> pool zou zonder plafond op `total` uitkomen en de
        # vec0-limiet met 1 overschrijden.
        #
        # Varieer de RICHTING, niet de lengte: vectoren worden genormaliseerd
        # opgeslagen, dus `[1-i*eps, 0, 0, 0]` collapst voor elke i naar
        # dezelfde eenheidsvector en maakt de volgorde willekeurig.
        rows = [(f"doc_{i:05d}.md", [1.0, i * 1e-4, 0.0, 0.0]) for i in range(4097)]
        for path, vec in rows:
            _kbindex.upsert(conn, path=path, layer="wiki", status="current",
                            body="corpus doc", vector=vec,
                            file_hash=path, created="2026-07-25")
        self.assertEqual(
            conn.execute("SELECT count(*) FROM docs").fetchone()[0], 4097)
        try:
            res = _kbindex.search(conn, query_vector=[1.0, 0.0, 0.0, 0.0], k=3)
        except sqlite3.OperationalError as exc:  # pragma: no cover - regressiepad
            self.fail(f"search() gooit boven de vec0-limiet: {exc}")
        finally:
            conn.close()
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]["path"], "doc_00000.md")


if __name__ == "__main__":
    unittest.main()


class MemoryLayerSkipsLexicalArmTest(unittest.TestCase):
    """RRF weighs both rankings equally, which only pays off when they are
    comparably strong.

    Measured over one index and the project's own eval sets (recall@5 / MRR):
    on wiki, dense 0.997/0.967 and fts 0.991/0.946 fuse to 1.000/0.984 -- the
    fusion beats both arms. On memory, dense 0.794/0.539 and fts 0.461/0.266
    fuse to 0.658/0.479 -- the fusion beats neither, because the weak lexical
    ranking pushes good dense hits out of the top k. Hence: no lexical arm on
    the memory layer, restorable with KB_MEMORY_FTS=1 for re-measurement.
    """

    def setUp(self):
        self.conn = _kbindex.connect(":memory:")
        _kbindex.ensure_schema(self.conn, dim=DIM, embed_id="ollama:test")
        # Lexically an exact hit for "vogelbekdier", but far away in vector
        # space. Only a lexical arm can put this first.
        _kbindex.upsert(self.conn, path="lexical.md", layer="memory", status="current",
                        body="vogelbekdier", vector=[0.90, 0.90, 0.90, 0.90],
                        file_hash="h1", created="2026-06-01")
        _kbindex.upsert(self.conn, path="dense.md", layer="memory", status="current",
                        body="niets gemeenschappelijks", vector=[0.10, 0.20, 0.30, 0.40],
                        file_hash="h2", created="2026-06-02")
        self._saved = os.environ.get("KB_MEMORY_FTS")
        os.environ.pop("KB_MEMORY_FTS", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KB_MEMORY_FTS", None)
        else:
            os.environ["KB_MEMORY_FTS"] = self._saved
        self.conn.close()

    def _paths(self, **kw):
        return [r["path"] for r in _kbindex.search(
            self.conn, query_vector=[0.10, 0.20, 0.30, 0.40], k=5, **kw)]

    def test_memory_only_query_ignores_the_lexical_ranking(self):
        paths = self._paths(query_text="vogelbekdier", layers=("memory",))
        self.assertEqual(paths[0], "dense.md",
                         "a term match outranked the vector hit on the memory layer")

    def test_the_lexical_arm_still_runs_for_other_layers(self):
        paths = self._paths(query_text="vogelbekdier", layers=("wiki", "memory"))
        self.assertIn("lexical.md", paths,
                      "a mixed-layer query lost its lexical half")

    def test_env_override_restores_the_lexical_arm(self):
        os.environ["KB_MEMORY_FTS"] = "1"
        rows = _kbindex.search(self.conn, query_vector=[0.10, 0.20, 0.30, 0.40],
                               k=5, query_text="vogelbekdier", layers=("memory",))
        self.assertTrue(any(r.get("fts") for r in rows),
                        "KB_MEMORY_FTS=1 did not bring the lexical arm back")
