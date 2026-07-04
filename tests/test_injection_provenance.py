"""Tests voor herkomst-tagging in de retrieval-injectie (TASK-20).

De retrieval-hook injecteert MEMORY-hits met een compacte, deterministische
herkomst/status-tag afgeleid van evidence_basis + status. WIKI-hits blijven
ongetagd (evergreen/gecureerd). Puur presentatie: geen filter/suppressie,
geen nieuw frontmatter-veld, geen LLM in het pad.

Drie testklassen, alle Ollama-vrij:

1. ProvenanceTagPureTest — de pure mapping _memory.provenance_tag
   (evidence_basis + status -> tag), inclusief fail-soft op onbekende basis.
2. MemoryBlockProvenanceTest — _memory_block met stub hits_fn + echte
   memory-bestanden op schijf: getypt leest autoritatief, agent/unverified
   krijgt een "onbevestigd"-markering.
3. WikiBlockUntaggedTest — _wiki_block met fake emb/kb_recall: wiki-hits
   krijgen NOOIT een "(bron: ...)"-tag.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK = SCRIPTS_DIR / "kb-retrieve.py"


def _load_kb_retrieve():
    spec = importlib.util.spec_from_file_location("kb_retrieve", str(HOOK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_memory():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(
        "_memory", str(SCRIPTS_DIR / "_memory.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_memory(path: Path, *, evidence_basis: str, status: str) -> None:
    fm = ["---",
          'title: "Testles"',
          "type: memory",
          f"status: {status}",
          f"evidence_basis: {evidence_basis}",
          "---",
          "",
          "Body van de memory.",
          ""]
    path.write_text("\n".join(fm), encoding="utf-8")


class ProvenanceTagPureTest(unittest.TestCase):
    """De pure (evidence_basis, status) -> tag mapping is deterministisch."""

    def setUp(self):
        self.mem = _load_memory()

    def test_getypt_current_is_authoritative_no_qualifier(self):
        self.assertEqual(self.mem.provenance_tag("getypt", "current"), "(bron: getypt)")

    def test_agent_current_reads_as_hint_not_unverified(self):
        # agent = autonome herkomst (hint), maar status=current is judge-geverifieerd
        # -> "autonoom" (origin-as) WEL, "onbevestigd" (status-as) NIET.
        self.assertEqual(self.mem.provenance_tag("agent", "current"),
                         "(bron: agent, autonoom)")

    def test_agent_unverified_gets_both_axes(self):
        self.assertEqual(self.mem.provenance_tag("agent", "unverified"),
                         "(bron: agent, autonoom, onbevestigd)")

    def test_human_in_loop_is_authoritative(self):
        self.assertEqual(self.mem.provenance_tag("cc-sessie", "current"),
                         "(bron: cc-sessie, mens-in-lus)")

    def test_unverified_status_adds_onbevestigd(self):
        self.assertEqual(self.mem.provenance_tag("getypt", "unverified"),
                         "(bron: getypt, onbevestigd)")

    def test_unknown_basis_fail_soft_empty(self):
        self.assertEqual(self.mem.provenance_tag("gok", "current"), "")
        self.assertEqual(self.mem.provenance_tag("", "current"), "")
        self.assertEqual(self.mem.provenance_tag(None, None), "")


class MemoryBlockProvenanceTest(unittest.TestCase):
    """_memory_block tagt elke memory-hit met de herkomst uit de frontmatter."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-prov-"))
        (self.tmp / ".claude").mkdir(parents=True, exist_ok=True)
        self._saved = os.environ.get("KENNISBANK_VAULT")
        os.environ["KENNISBANK_VAULT"] = str(self.tmp)
        self.mod = _load_kb_retrieve()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _block(self, hits):
        return self.mod._memory_block(
            [0.1, 0.2], "test prompt", {}, hits_fn=lambda *a, **k: hits)

    def test_getypt_memory_gets_authoritative_tag(self):
        p = self.tmp / "getypt.md"
        _write_memory(p, evidence_basis="getypt", status="current")
        out = self._block([{"path": str(p), "score": 0.9, "snippet": "iets"}])
        self.assertIn("[[getypt]]", out)
        self.assertIn("(bron: getypt)", out)
        self.assertNotIn("onbevestigd", out)

    def test_agent_current_memory_gets_autonoom_not_onbevestigd(self):
        p = self.tmp / "agent.md"
        _write_memory(p, evidence_basis="agent", status="current")
        out = self._block([{"path": str(p), "score": 0.8, "snippet": "gok"}])
        self.assertIn("[[agent]]", out)
        self.assertIn("(bron: agent, autonoom)", out)
        self.assertNotIn("onbevestigd", out)  # current = judge-geverifieerd

    def test_unverified_human_in_loop_marks_onbevestigd(self):
        p = self.tmp / "sessie.md"
        _write_memory(p, evidence_basis="cc-sessie", status="unverified")
        out = self._block([{"path": str(p), "score": 0.7, "snippet": "x"}])
        self.assertIn("(bron: cc-sessie, mens-in-lus, onbevestigd)", out)

    def test_missing_evidence_basis_no_tag_no_crash(self):
        p = self.tmp / "bare.md"
        p.write_text("---\ntitle: \"Kaal\"\nstatus: current\n---\n\nBody.\n",
                     encoding="utf-8")
        out = self._block([{"path": str(p), "score": 0.6, "snippet": "y"}])
        self.assertIn("[[bare]]", out)
        self.assertNotIn("(bron:", out)

    def test_mixed_hits_tagged_independently(self):
        pg = self.tmp / "typed.md"
        pa = self.tmp / "auto.md"
        _write_memory(pg, evidence_basis="getypt", status="current")
        _write_memory(pa, evidence_basis="agent", status="current")
        out = self._block([
            {"path": str(pg), "score": 0.9, "snippet": "a"},
            {"path": str(pa), "score": 0.5, "snippet": "b"},
        ])
        self.assertIn("[[typed]] (0.90) (bron: getypt): a", out)
        self.assertIn("[[auto]] (0.50) (bron: agent, autonoom): b", out)


class _FakeEmb:
    """Minimale emb-stub voor _wiki_block (geen Ollama, geen cache-bestand)."""

    def __init__(self, wiki_key):
        self._key = wiki_key

    def load_cache(self):
        return {self._key: {"id": "prov:model", "embedding": [0.1], "dim": 1}}

    def embed_id(self):
        return "prov:model"

    def embed(self, prompt, timeout=None):
        return [0.1]

    def cosine(self, a, b):
        return 0.99

    def doc_text(self, p, cap=280):
        return "wiki snippet"


class _FakeRecall:
    def has_fts_match(self, *a, **k):
        return False

    def wiki_hits(self, qvec, query_text="", k=3, expand=False):
        return [{"path": "/vault/02-wiki/foo.md", "score": 0.9,
                 "snippet": "wiki snippet"}]


class WikiBlockUntaggedTest(unittest.TestCase):
    """Wiki-hits mogen NOOIT een herkomst-tag krijgen (evergreen/gecureerd)."""

    def setUp(self):
        self.mod = _load_kb_retrieve()

    def test_wiki_block_has_no_provenance_tag(self):
        vault = Path("/vault")
        wiki_key = str(vault / "02-wiki" / "foo.md")
        fake_emb = _FakeEmb(wiki_key)
        self.mod.kb_recall = _FakeRecall()
        text, qvec = self.mod._wiki_block(
            "een prompt over foo en bar in de wiki", fake_emb, lambda: vault, {})
        self.assertIn("[[foo]]", text)
        self.assertNotIn("(bron:", text)
        self.assertNotIn("onbevestigd", text)


if __name__ == "__main__":
    unittest.main()
