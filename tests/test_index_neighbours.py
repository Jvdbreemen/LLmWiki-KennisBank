"""Half an hour of CPU per sweep to find ten pairs.

`similar_pairs` compared every current memory with every other one: 1,271,215
cosines in pure Python, measured at 15m26s on the live vault. `neighbor_counts`
walked the same triangle again. That is heavy work that runs every time and
finds almost nothing, and it grows quadratically (TASK-154).

The index already holds exactly these vectors in a structure built for this
question. What these tests hold is the part that makes the shortcut safe: the
answer must be the SAME as brute force, and the fallback must survive every way
the index can be unusable.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import _embeddings as emb  # noqa: E402
import _kbindex  # noqa: E402
import _maintenance as mnt  # noqa: E402

try:
    import sqlite_vec  # noqa: F401
    HAS_VEC = True
except Exception:
    HAS_VEC = False


def _vec(*xs):
    return [float(x) for x in xs]


@unittest.skipUnless(HAS_VEC, "sqlite-vec is not installed")
class IndexNeighbourTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-knn-"))
        (self.tmp / ".claude").mkdir(parents=True)
        (self.tmp / "09-memory").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.items = []

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_index(self, vectors, *, embed_id=None, unit_norm=True, layer="memory"):
        """Write an index holding `vectors` ({name: vec}) and set self.items."""
        conn = _kbindex.connect(self.tmp / ".claude" / "kb-index.db")
        dim = len(next(iter(vectors.values())))
        _kbindex.ensure_schema(conn, dim=dim, embed_id=embed_id or emb.embed_id())
        _kbindex.set_unit_norm(conn, unit_norm)
        for name, v in vectors.items():
            path = str(self.tmp / "09-memory" / f"{name}.md")
            _kbindex.upsert(conn, path=path, layer=layer, status="current",
                            body=name, vector=v, file_hash=name,
                            title=name, created="2026-01-01", sources="")
            self.items.append({"path": path, "vec": v, "body": name,
                               "volatility": "state", "created": "2026-01-01",
                               "valid_from": "2026-01-01", "status": "current"})
        conn.close()

    # -- the shortcut agrees with the long way ------------------------------
    def test_the_index_finds_the_same_pairs_as_brute_force(self):
        """A faster pass that finds different pairs is a behaviour change."""
        self._build_index({
            "a": _vec(1, 0, 0),
            "b": _vec(0.99, 0.141, 0),     # cos ~0.99 with a
            "c": _vec(0, 1, 0),            # orthogonal to a
            "d": _vec(0.1, 0.995, 0),      # cos ~0.995 with c
        })
        for threshold in (0.5, 0.75, 0.9):
            with self.subTest(threshold=threshold):
                fast = mnt.similar_pairs(self.items, threshold)
                # Force the brute-force path by hiding the index.
                orig = mnt._neighbours_from_index
                mnt._neighbours_from_index = lambda *a, **k: None
                try:
                    slow = mnt.similar_pairs(self.items, threshold)
                finally:
                    mnt._neighbours_from_index = orig

                def key(pairs):
                    return sorted({tuple(sorted((a["path"], b["path"])))
                                   for a, b, _s in pairs})
                self.assertEqual(key(fast), key(slow))

    def test_the_counts_agree_too(self):
        self._build_index({
            "a": _vec(1, 0, 0),
            "b": _vec(0.99, 0.141, 0),
            "c": _vec(0, 1, 0),
        })
        fast = mnt.neighbor_counts(self.items, 0.5)
        orig = mnt._neighbours_from_index
        mnt._neighbours_from_index = lambda *a, **k: None
        try:
            slow = mnt.neighbor_counts(self.items, 0.5)
        finally:
            mnt._neighbours_from_index = orig
        self.assertEqual(fast, slow)

    def test_a_pair_is_reported_once_not_twice(self):
        """Both sides see each other; the pair list must not double."""
        self._build_index({"a": _vec(1, 0, 0), "b": _vec(0.99, 0.141, 0)})
        self.assertEqual(len(mnt.similar_pairs(self.items, 0.5)), 1)

    def test_a_memory_is_not_its_own_neighbour(self):
        self._build_index({"a": _vec(1, 0, 0)})
        self.assertEqual(mnt.similar_pairs(self.items, 0.5), [])
        self.assertEqual(mnt.neighbor_counts(self.items, 0.5)[self.items[0]["path"]], 0)

    def test_the_window_widens_rather_than_truncating(self):
        """A fixed k would silently drop neighbours past the window.

        With the probe forced down to 1, every item has more neighbours above
        the threshold than the window holds. If the loop did not widen, the
        result would quietly be incomplete -- exactly the failure this codebase
        keeps removing.
        """
        self._build_index({f"m{i}": _vec(1, i * 0.001, 0) for i in range(12)})
        orig = mnt.INDEX_PROBE_K
        mnt.INDEX_PROBE_K = 1
        try:
            narrow = mnt.similar_pairs(self.items, 0.5)
        finally:
            mnt.INDEX_PROBE_K = orig
        wide = mnt.similar_pairs(self.items, 0.5)
        self.assertEqual(len(narrow), len(wide))
        self.assertEqual(len(wide), 12 * 11 // 2)

    # -- every way the shortcut has to decline ------------------------------
    def test_no_index_falls_back(self):
        self.items = [{"path": "a", "vec": _vec(1, 0, 0)},
                      {"path": "b", "vec": _vec(1, 0, 0)}]
        self.assertIsNone(mnt._neighbours_from_index(self.items, 0.5))
        self.assertEqual(len(mnt.similar_pairs(self.items, 0.5)), 1,
                         "de brute weg moet het antwoord alsnog geven")

    def test_a_different_embedding_space_falls_back(self):
        """Cosine across two models means nothing, so this must not be used."""
        self._build_index({"a": _vec(1, 0, 0), "b": _vec(0.99, 0.141, 0)},
                          embed_id="ollama:some-other-model")
        self.assertIsNone(mnt._neighbours_from_index(self.items, 0.5))
        self.assertEqual(len(mnt.similar_pairs(self.items, 0.5)), 1)

    def test_an_unnormalised_index_falls_back(self):
        """distance -> cosine only holds for unit vectors.

        A wrong cosine here decides whether memories get closed, so guessing is
        not an option.
        """
        self._build_index({"a": _vec(1, 0, 0), "b": _vec(0.99, 0.141, 0)},
                          unit_norm=False)
        self.assertIsNone(mnt._neighbours_from_index(self.items, 0.5))

    def _unindexed(self, name, vec):
        path = str(self.tmp / "09-memory" / f"{name}.md")
        self.items.append({"path": path, "vec": vec, "body": name,
                           "volatility": "state", "created": "2026-01-01",
                           "valid_from": "2026-01-01", "status": "current"})
        return path

    def test_a_memory_missing_from_the_index_is_still_compared(self):
        """The index lags the filesystem by construction after every sweep."""
        self._build_index({"a": _vec(1, 0, 0)})
        self._unindexed("b", _vec(0.99, 0.141, 0))
        self.assertEqual(len(mnt.similar_pairs(self.items, 0.5)), 1)

    def test_two_memories_the_index_has_never_seen_still_find_each_other(self):
        """The gap that makes a naive index shortcut silently incomplete.

        A sweep writes memories and the index catches up afterwards, so
        "neither side is indexed yet" is the normal state for anything just
        captured -- exactly the memories a reconcile pass cares about most.
        Querying the index alone would return nothing for both and report a
        clean zero.
        """
        self._build_index({"far": _vec(0, 0, 1)})
        self._unindexed("new1", _vec(1, 0, 0))
        self._unindexed("new2", _vec(0.99, 0.141, 0))

        pairs = mnt.similar_pairs(self.items, 0.5)
        got = {tuple(sorted((a["path"], b["path"]))) for a, b, _s in pairs}
        expected = {tuple(sorted((self.items[1]["path"], self.items[2]["path"])))}
        self.assertEqual(got, expected)

    def test_the_hybrid_counts_a_pair_once(self):
        """The loose arm writes both directions; the index may report it too."""
        self._build_index({"a": _vec(1, 0, 0)})
        self._unindexed("b", _vec(0.99, 0.141, 0))
        counts = mnt.neighbor_counts(self.items, 0.5)
        self.assertEqual(set(counts.values()), {1},
                         "een dubbel geteld paar laat neighbor_counts liegen")

    def test_the_hybrid_still_agrees_with_brute_force(self):
        self._build_index({"a": _vec(1, 0, 0), "c": _vec(0, 1, 0)})
        self._unindexed("b", _vec(0.99, 0.141, 0))
        self._unindexed("d", _vec(0.1, 0.995, 0))

        fast = mnt.similar_pairs(self.items, 0.5)
        orig = mnt._neighbours_from_index
        mnt._neighbours_from_index = lambda *a, **k: None
        try:
            slow = mnt.similar_pairs(self.items, 0.5)
        finally:
            mnt._neighbours_from_index = orig

        def key(pairs):
            return sorted({tuple(sorted((a["path"], b["path"]))) for a, b, _s in pairs})
        self.assertEqual(key(fast), key(slow))

    def test_documents_from_other_layers_are_not_neighbours(self):
        """The index holds every layer; this pass is about memories only."""
        self._build_index({"a": _vec(1, 0, 0)})
        conn = _kbindex.connect(self.tmp / ".claude" / "kb-index.db")
        _kbindex.upsert(conn, path=str(self.tmp / "02-wiki" / "artikel.md"),
                        layer="wiki", status="current", body="artikel",
                        vector=_vec(1, 0, 0), file_hash="w",
                        title="artikel", created="2026-01-01", sources="")
        conn.close()
        self.assertEqual(mnt.similar_pairs(self.items, 0.5), [])


if __name__ == "__main__":
    unittest.main()
