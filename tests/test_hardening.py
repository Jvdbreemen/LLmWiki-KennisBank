"""Tests voor de structurele hardening (TASK-90, Spoor E).

- E4a: weigering-/lege-evidence-poort in _extract (arkon#25-replay);
- E4b: geen netwerk tijdens deterministische ingest-paden (arkon#29);
- E5: producent-provenance (model_id + prompt_version) render/parse-roundtrip;
- E2/E6: kb-lint self-source (HARD) + index-drift (advisory) fixtures.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _extract  # noqa: E402
import _memory  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402

from tests._loader import load_script  # noqa: E402


class RefusalGateTest(unittest.TestCase):
    """E4a: 'ik kan dit niet beantwoorden' mag nooit kennis worden."""

    def test_refusal_markers_detected(self):
        for txt in ("Ik kan deze vraag niet beantwoorden.",
                    "I'm sorry, I cannot help with that.",
                    "Als AI heb ik geen toegang tot je systeem.",
                    "As a language model I don't have access to that."):
            self.assertTrue(_extract.looks_like_refusal(txt), txt)

    def test_real_knowledge_passes(self):
        for txt in ("WireGuard achter CGNAT vereist een VPS-relay.",
                    "De busy-timeout stond op 5s; dat loste de lock op.",
                    "Besloten: kb-graph.db krijgt een eigen bestand."):
            self.assertFalse(_extract.looks_like_refusal(txt), txt)

    def test_arkon25_replay_refusal_never_persisted(self):
        """De arkon#25-faalwijze nagespeeld: de LLM antwoordt met een
        weigering als 'kandidaat' — de poort breekt de schrijfactie af."""
        refusal_json = json.dumps([{
            "title": "Antwoord niet mogelijk",
            "body": "Ik kan deze vraag niet beantwoorden zonder meer context.",
            "type": "feit",
        }, {
            "title": "Echte les",
            "body": "De WAL-mode voorkomt reader-blokkades bij concurrent sweeps.",
            "type": "feit",
        }])
        with patch.object(_extract._llm, "generate", return_value=refusal_json):
            out = _extract.extract_candidates("transcripttekst")
        self.assertEqual([c["title"] for c in out], ["Echte les"])

    def test_empty_transcript_yields_nothing(self):
        self.assertEqual(_extract.extract_candidates("   "), [])

    def test_prompt_version_constant_exists(self):
        self.assertIsInstance(_extract.EXTRACT_PROMPT_VERSION, int)
        self.assertGreaterEqual(_extract.EXTRACT_PROMPT_VERSION, 1)


class ProducerProvenanceTest(unittest.TestCase):
    """E5: model_id + prompt_version overleven een render/parse-roundtrip."""

    def test_roundtrip(self):
        md = _memory.render("Titel", "Body.", model_id="ollama/qwen3:8b",
                            prompt_version=3)
        fm, _ = parse_frontmatter(md)
        self.assertEqual(fm.get("model_id"), "ollama/qwen3:8b")
        self.assertEqual(str(fm.get("prompt_version")), "3")

    def test_absent_by_default(self):
        md = _memory.render("Titel", "Body.")
        fm, _ = parse_frontmatter(md)
        self.assertNotIn("model_id", fm)
        self.assertNotIn("prompt_version", fm)


class SelfSourceLintTest(unittest.TestCase):
    """E6: een conclusie mag nooit als bron/bewijs terugvloeien (llm_wiki #538)."""

    def setUp(self):
        self.kl = load_script("kb-lint.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "01-raw" / "sessies").mkdir(parents=True)
        (self.root / "02-wiki").mkdir()
        (self.root / "01-raw" / "sessies" / "raw-sessie-2026-07-01-x.md").write_text(
            "sessielog", encoding="utf-8")

    def _findings(self, name, body):
        (self.root / "02-wiki" / name).write_text(body, encoding="utf-8")
        return self.kl.lint_article(self.root / "02-wiki" / name,
                                    self.kl.collect_session_stems(self.root),
                                    self.root)

    def test_wiki_article_as_herkomst_is_hard(self):
        f = self._findings("a.md",
                           "inhoud\n\n## Sessie-herkomst\n"
                           "- punt: [[02-wiki/ander-artikel.md]]\n"
                           "- punt: [[raw-sessie-2026-07-01-x]]\n")
        self.assertIn("self-source", [x["type"] for x in f])
        self.assertIn("self-source", self.kl.HARD_TYPES)

    def test_system_file_as_herkomst_is_hard(self):
        f = self._findings("b.md",
                           "inhoud\n\n## Sessie-herkomst\n"
                           "- punt: [[.claude/scripts/log.md]]\n"
                           "- punt: [[raw-sessie-2026-07-01-x]]\n")
        self.assertIn("self-source", [x["type"] for x in f])

    def test_wiki_link_outside_herkomst_section_is_fine(self):
        f = self._findings("c.md",
                           "## Verbanden\n- [[02-wiki/ander-artikel.md]]\n\n"
                           "## Sessie-herkomst\n- punt: [[raw-sessie-2026-07-01-x]]\n")
        self.assertEqual([x for x in f if x["type"] == "self-source"], [])


class IndexDriftLintTest(unittest.TestCase):
    """E2: ghost-docs in de index horen zichtbaar te zijn (llm_wiki #580)."""

    def setUp(self):
        self.kl = load_script("kb-lint.py")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "02-wiki").mkdir(parents=True)
        (self.root / ".claude").mkdir()

    def _build_index(self, paths):
        import _kbindex
        conn = _kbindex.connect(str(self.root / ".claude" / "kb-index.db"))
        _kbindex.ensure_schema(conn, dim=4, embed_id="ollama:test")
        for p in paths:
            _kbindex.upsert(conn, path=str(p), layer="wiki", status="current",
                            body="x", vector=[0.1, 0.2, 0.3, 0.4], file_hash="h")
        conn.close()

    def test_ghost_doc_reported_advisory(self):
        live = self.root / "02-wiki" / "bestaat.md"
        live.write_text("x", encoding="utf-8")
        self._build_index([live, self.root / "02-wiki" / "weg.md"])
        findings = self.kl.lint_index_drift(self.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], "index-drift")
        self.assertNotIn("index-drift", self.kl.HARD_TYPES)

    def test_clean_index_no_findings(self):
        live = self.root / "02-wiki" / "bestaat.md"
        live.write_text("x", encoding="utf-8")
        self._build_index([live])
        self.assertEqual(self.kl.lint_index_drift(self.root), [])

    def test_missing_db_failsoft(self):
        self.assertEqual(self.kl.lint_index_drift(self.root), [])


class NoNetworkDuringIngestTest(unittest.TestCase):
    """E4b (arkon#29): de deterministische ingest-paden doen NUL netwerk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        for d in ("00-inbox", "01-raw/sessies", "02-wiki", "09-memory"):
            (self.vault / d).mkdir(parents=True)
        (self.vault / "00-inbox" / "nota.md").write_text("# nota\n", encoding="utf-8")
        (self.vault / "01-raw" / "sessies" / "raw-sessie-2099-01-01-x.md").write_text(
            "wiki-kandidaat: onderwerp\n", encoding="utf-8")
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_deterministic_ingest_paths_make_no_network_calls(self):
        def boom(*a, **kw):
            raise AssertionError("netwerk-call tijdens deterministische ingest")
        with patch.object(socket, "socket", side_effect=boom), \
             patch.object(socket, "create_connection", side_effect=boom):
            intake = load_script("intake-scan.py")
            r1 = intake.scan()
            self.assertGreaterEqual(r1["total"], 1)
            ws = load_script("wiki-scan.py")
            r2 = ws.scan(self.vault, days=36500, similar_fn=None)
            self.assertGreaterEqual(r2["total"], 1)
            import _provenance
            srcs = _provenance.doc_sources(
                Path("a.md"), "wiki", {}, "[[raw-sessie-2099-01-01-x]]")
            self.assertEqual(srcs, ["raw-sessie-2099-01-01-x"])


if __name__ == "__main__":
    unittest.main()
