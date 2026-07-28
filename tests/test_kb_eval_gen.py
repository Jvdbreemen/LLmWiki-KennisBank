"""Tests voor scripts/kb-eval-gen.py — kandidaat-generator voor eval-sets (TASK-86).

Puur deterministisch getest: geen LLM, geen index. De drie harde eisen:
determinisme, draft-isolatie (live sets onaanraakbaar) en schema-compatibiliteit
met kb-eval.load_set.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._loader import load_script


def _gen():
    return load_script("kb-eval-gen.py")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class EvalGenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.g = _gen()

        _write(self.vault / "02-wiki" / "wireguard-cgnat.md",
               "---\ntitle: WireGuard achter CGNAT\ntags: [wireguard, mikrotik]\n---\n\n"
               "## Opzet\nInhoud.\n")
        _write(self.vault / "02-wiki" / "zonder-tags.md",
               "---\ntitle: Artikel zonder tags\n---\n\n## Eerste kop\nInhoud.\n")
        _write(self.vault / "02-wiki" / "index.md", "# index\n")
        _write(self.vault / "09-memory" / "2026-07-01-besluit-x.md",
               "---\ntitle: Besluit over X\nmemory_type: beslissing\nstatus: current\n---\n\nX.\n")
        _write(self.vault / "09-memory" / "2026-07-02-oud.md",
               "---\ntitle: Ingetrokken ding\nmemory_type: feit\nstatus: retracted\n---\n\nY.\n")

    # --- determinisme ---

    def test_two_runs_are_identical(self):
        a = self.g.generate(self.vault, "wiki")
        b = self.g.generate(self.vault, "wiki")
        self.assertEqual(a, b)
        self.assertTrue(a)

    # --- wiki-kandidaten ---

    def test_wiki_has_title_and_keyword_questions(self):
        entries = self.g.generate(self.vault, "wiki")
        types = {(e["expect"][0], e["type"]) for e in entries}
        self.assertIn(("wireguard-cgnat", "single-hop"), types)
        self.assertIn(("wireguard-cgnat", "keyword"), types)

    def test_wiki_without_tags_falls_back_to_heading(self):
        entries = [e for e in self.g.generate(self.vault, "wiki")
                   if e["expect"] == ["zonder-tags"]]
        self.assertEqual(len(entries), 2)
        self.assertTrue(any("Eerste kop" in e["q"] for e in entries))

    def test_wiki_skips_index_and_log(self):
        entries = self.g.generate(self.vault, "wiki")
        self.assertFalse(any(e["expect"] == ["index"] for e in entries))

    # --- memory-kandidaten ---

    def test_memory_only_current_and_typed(self):
        entries = self.g.generate(self.vault, "memory")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["expect"], ["2026-07-01-besluit-x"])
        self.assertEqual(entries[0]["type"], "beslissing")
        self.assertIn("besloten", entries[0]["q"].lower())

    # --- draft-isolatie ---

    def test_write_draft_refuses_live_set_path(self):
        with self.assertRaises(ValueError):
            self.g.write_draft(Path(self.tmp.name) / "kb-eval-set.json", [])

    def test_write_draft_writes_draft_json(self):
        p = Path(self.tmp.name) / "kb-eval-set.draft.json"
        self.g.write_draft(p, [{"q": "v?", "expect": ["a"], "type": "keyword"}])
        self.assertTrue(p.exists())

    def test_draft_never_named_like_live_set(self):
        for layer in ("wiki", "memory"):
            p = self.g.draft_path(Path(self.tmp.name), layer)
            self.assertTrue(p.name.endswith(".draft.json"))

    # --- schema-compatibiliteit met het harnas ---

    def test_output_loads_via_kb_eval_load_set(self):
        ev = load_script("kb-eval.py")
        entries = self.g.generate(self.vault, "wiki")
        p = Path(self.tmp.name) / "kb-eval-set.draft.json"
        self.g.write_draft(p, entries)
        loaded = ev.load_set(p)
        self.assertEqual(len(loaded), len(entries))

    # --- LLM-laag is fail-soft ---

    def test_paraphrase_returns_empty_on_error(self):
        # _llm faalt -> lege string, nooit een exceptie. Fout expliciet
        # geinjecteerd: op een machine met draaiende Ollama zou een echte
        # aanroep anders een geldig antwoord (of 60s wachttijd) geven.
        import sys as _sys
        scripts = Path(__file__).resolve().parent.parent / "scripts"
        if str(scripts) not in _sys.path:
            _sys.path.insert(0, str(scripts))
        import _llm
        with patch.object(_llm, "generate", side_effect=Exception("boom")):
            self.assertEqual(self.g._paraphrase("titel", "snippet"), "")


if __name__ == "__main__":
    unittest.main()
