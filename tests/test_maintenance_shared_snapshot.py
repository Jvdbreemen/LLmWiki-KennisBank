"""One corpus snapshot and one neighbour map per sweep (TASK-191).

supersede_pass, recheck_pass and cluster_promote_pass each reloaded the full
~1600-file corpus plus the whole vector table, and the neighbour probe ran
twice. Sharing is exactly equivalent only under two guards, both pinned here:
the snapshot is pruned of what each pass closed (so the next pass sees the
same world a fresh reload would show), and a map computed at a lower
threshold or wider item set filters exactly (strict '>' everywhere,
membership filters on the current item list).

Also here: the index hash gate. _index_vectors now returns (file_hash,
vector) and current_items serves the index vector only when that hash matches
the file AS IT IS NOW — the index lags the filesystem by design, and an
edited memory used to be judged with the embedding of its previous content.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import _embeddings as emb  # noqa: E402
import _maintenance as mnt  # noqa: E402


def _vec(*xs):
    return [float(x) for x in xs]


class SharedSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-snap-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        (self.tmp / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mem(self, name, vec, body="Waarde X = 1.", valid_from="2026-01-01"):
        p = self.tmp / "09-memory" / f"{name}.md"
        p.write_text(f"---\ntitle: {name}\ntype: memory\nstatus: current\n"
                     f"volatility: state\ncreated: {valid_from}\n"
                     f"valid_from: {valid_from}\n---\n\n{body}\n",
                     encoding="utf-8")
        return {"path": str(p), "vec": vec, "body": body, "status": "current",
                "volatility": "state", "created": valid_from,
                "valid_from": valid_from, "title": name}

    def test_shared_items_skip_the_reload(self):
        calls = []
        orig = mnt.current_items
        mnt.current_items = lambda *a, **k: calls.append(1) or orig(*a, **k)
        try:
            shared = [self._mem("a", _vec(1, 0))]
            mnt.supersede_pass(judge_fn=lambda n, o: False, items=shared)
            mnt.recheck_pass(judge_fn=lambda t: False, items=shared)
            mnt.cluster_promote_pass(items=shared)
            self.assertEqual(len(calls), 0)
            mnt.recheck_pass(judge_fn=lambda t: False)
            self.assertEqual(len(calls), 1)  # default pad intact
        finally:
            mnt.current_items = orig

    def test_supersede_prunes_what_it_closed_from_the_shared_list(self):
        a = self._mem("a", _vec(1.0, 0.0), valid_from="2026-01-02")
        b = self._mem("b", _vec(0.999, 0.045), valid_from="2026-01-01")
        shared = [a, b]
        done = mnt.supersede_pass(threshold=0.5, judge_fn=lambda n, o: True,
                                  items=shared)
        self.assertEqual(done, 1)
        self.assertEqual([it["title"] for it in shared], ["a"],
                         "de gesloten memory moet uit de gedeelde lijst")

    def test_recheck_prunes_what_it_retracted(self):
        shared = [self._mem("a", _vec(1, 0)), self._mem("b", _vec(0, 1))]
        done = mnt.recheck_pass(judge_fn=lambda t: True, limit=1, items=shared)
        self.assertEqual(done, 1)
        self.assertEqual(len(shared), 1)

    def test_a_lower_threshold_map_filters_exactly(self):
        """Map op 0.5, gebruikt op 0.8: identiek aan een verse 0.8-berekening."""
        items = [self._mem("a", _vec(1, 0)),
                 self._mem("b", _vec(0.9, 0.436)),   # cos ~0.9 met a
                 self._mem("c", _vec(0.6, 0.8))]     # cos 0.6 met a
        wide = mnt.neighbour_map(items, 0.5)
        self.assertEqual(mnt.neighbor_counts(items, 0.8, neighbours=wide),
                         mnt.neighbor_counts(items, 0.8))
        self.assertEqual(
            [(a["title"], b["title"], round(c, 3))
             for a, b, c in mnt.similar_pairs(items, 0.8, neighbours=wide)],
            [(a["title"], b["title"], round(c, 3))
             for a, b, c in mnt.similar_pairs(items, 0.8)])

    def test_a_pruned_item_set_filters_membership(self):
        items = [self._mem("a", _vec(1, 0)), self._mem("b", _vec(0.99, 0.141)),
                 self._mem("c", _vec(0.98, 0.199))]
        nmap = mnt.neighbour_map(items, 0.5)
        survivors = [it for it in items if it["title"] != "b"]
        counts = mnt.neighbor_counts(survivors, 0.5, neighbours=nmap)
        self.assertNotIn(items[1]["path"], counts)
        self.assertEqual(counts, mnt.neighbor_counts(survivors, 0.5))


class IndexHashGateTest(unittest.TestCase):
    """current_items serves an index vector only when the stored hash matches."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-hashgate-"))
        (self.tmp / "09-memory").mkdir(parents=True)
        (self.tmp / ".claude").mkdir(parents=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.p = self.tmp / "09-memory" / "m.md"
        self.p.write_text("---\ntitle: m\ntype: memory\nstatus: current\n"
                          "created: 2026-01-01\n---\n\nInhoud.\n",
                          encoding="utf-8")
        self._orig_iv = mnt._index_vectors

    def tearDown(self):
        mnt._index_vectors = self._orig_iv
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_stale_hash_falls_back_to_the_cache_path(self):
        mnt._index_vectors = lambda: {str(self.p): ("stale123", [1.0, 0.0])}
        sentinel = [0.0, 1.0]
        items = mnt.current_items(
            get_cached_fn=lambda p, cache, recompute=True: sentinel)
        self.assertEqual(items[0]["vec"], sentinel,
                         "een verouderde indexvector mag nooit geserveerd worden")

    def test_a_matching_hash_serves_the_index_vector(self):
        good = emb.file_hash(self.p)
        mnt._index_vectors = lambda: {str(self.p): (good, [1.0, 0.0])}

        def _boom(p, cache, recompute=True):
            raise AssertionError("fallback aangeroepen terwijl de hash klopte")
        items = mnt.current_items(get_cached_fn=_boom)
        self.assertEqual(items[0]["vec"], [1.0, 0.0])

    def test_editing_the_file_invalidates_the_index_vector(self):
        good = emb.file_hash(self.p)
        mnt._index_vectors = lambda: {str(self.p): (good, [1.0, 0.0])}
        self.p.write_text(self.p.read_text(encoding="utf-8") + "Nieuwe regel.\n",
                          encoding="utf-8")
        sentinel = [0.5, 0.5]
        items = mnt.current_items(
            get_cached_fn=lambda p, cache, recompute=True: sentinel)
        self.assertEqual(items[0]["vec"], sentinel)


if __name__ == "__main__":
    unittest.main()
