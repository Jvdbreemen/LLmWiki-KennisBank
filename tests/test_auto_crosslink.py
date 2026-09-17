"""A graph node may carry source_file: null, and the crosslinker must skip it.

graphify's link layer writes tag and reference nodes with an explicit
``"source_file": null``. ``dict.get(key, "")`` returns None for those -- the
default only applies when the key is ABSENT -- so the next ``.startswith``
raised ``AttributeError: 'NoneType' object has no attribute 'startswith'`` and
every run after a ``graphify --update`` died. Reported against a vault of 2076
nodes, 232 of them without a source file (PR #169).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_script  # noqa: E402


class NullSourceFileTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_script("auto-crosslink.py")
        self.tmp = tempfile.TemporaryDirectory(prefix="kb-crosslink-")
        self.vault = Path(self.tmp.name)
        (self.vault / "02-wiki").mkdir(parents=True)
        self.mod.VAULT_ROOT = self.vault
        self.addCleanup(self.tmp.cleanup)

    def _article(self, name: str, body: str) -> Path:
        p = self.vault / "02-wiki" / name
        p.write_text(body, encoding="utf-8")
        return p

    def _graph(self):
        """One article node, one wiki neighbour, one link-layer tag node."""
        node_map = {
            "n1": {"source_file": "02-wiki/bron.md"},
            "n2": {"source_file": "02-wiki/buur.md"},
            "tag1": {"source_file": None},          # the link layer's own node
        }
        links = [
            {"source": "n1", "target": "tag1", "confidence_score": 0.99,
             "relation": "heeft_tag"},
            {"source": "n1", "target": "n2", "confidence_score": 0.90,
             "relation": "zie_ook"},
        ]
        return node_map, links

    def test_a_node_without_a_source_file_is_skipped_instead_of_crashing(self):
        article = self._article("bron.md", "# Bron\n\nTekst.\n")
        node_map, links = self._graph()
        self.mod.process_file(article, node_map, links, dry_run=False)
        self.assertIn("[[buur]]", article.read_text(encoding="utf-8"))

    def test_the_null_node_never_becomes_a_backlink(self):
        article = self._article("bron.md", "# Bron\n\nTekst.\n")
        node_map, links = self._graph()
        node_map["tag1"]["name"] = "journalistiek"
        self.mod.process_file(article, node_map, links, dry_run=False)
        text = article.read_text(encoding="utf-8")
        self.assertNotIn("journalistiek", text)
        self.assertEqual(text.count("Zie ook:"), 1)

    def test_a_dry_run_over_a_null_node_writes_nothing(self):
        before = "# Bron\n\nTekst.\n"
        article = self._article("bron.md", before)
        node_map, links = self._graph()
        self.mod.process_file(article, node_map, links, dry_run=True)
        self.assertEqual(article.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
