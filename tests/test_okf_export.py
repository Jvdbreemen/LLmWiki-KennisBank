"""Tests voor scripts/kb-okf-export.py — OKF v0.2-bundle als gerenderde view (TASK-92).

Conformantie per spec par. 11 op een fixture-vault: frontmatter + non-empty
type op elk concept, reserved filenames gerespecteerd, linkvorm,
trust-tier-mapping en byte-idempotentie.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._loader import load_script

try:
    import yaml  # PyYAML: strikte parser als scheidsrechter
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False


def _okf():
    return load_script("kb-okf-export.py")


class OkfExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "02-wiki").mkdir(parents=True)
        (self.vault / "09-memory").mkdir(parents=True)
        (self.vault / ".claude").mkdir(parents=True)
        self._env = patch.dict(os.environ, {"KENNISBANK_VAULT": str(self.vault)})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.m = _okf()
        self.out = Path(self.tmp.name) / "bundle"

        (self.vault / "02-wiki" / "wireguard.md").write_text(
            "---\ntitle: WireGuard achter CGNAT\ntype: wiki\n"
            "tags: [vpn, netwerk]\nstatus: evergreen\ncreated: 2026-07-01\n"
            "updated: 2026-07-02\n---\n\n"
            "Een VPS-relay lost CGNAT op. Zie [[traefik|de proxy]] en "
            "[[onbekend-artikel]].\n\n## Sessie-herkomst\n"
            "- punt: [[raw-sessie-2026-07-01-vpn]]\n", encoding="utf-8")
        (self.vault / "02-wiki" / "traefik.md").write_text(
            "---\ntitle: Traefik\ntype: wiki\ncreated: 2026-07-01\n---\n\n"
            "Reverse proxy met automatische certificaten.\n", encoding="utf-8")
        (self.vault / "09-memory" / "2026-07-01-besluit.md").write_text(
            "---\ntitle: 'Besluit: eigen graafbestand'\ntype: memory\n"
            "memory_type: beslissing\nimportance: 4\nstatus: current\n"
            "evidence_basis: agent\nsource_session: t1.jsonl.md\n"
            "created: 2026-07-01\nupdated: 2026-07-01\nvalid_from: 2026-07-01\n"
            "model_id: 'ollama/qwen3:8b'\nprompt_version: 1\ntags: []\n---\n\n"
            "kb-graph.db staat los van kb-index.db.\n", encoding="utf-8")
        (self.vault / "09-memory" / "2026-07-02-open.md").write_text(
            "---\ntitle: Nog onbevestigd\ntype: memory\nmemory_type: feit\n"
            "importance: 3\nstatus: unverified\nevidence_basis: agent\n"
            "source_session: t2.jsonl.md\ncreated: 2026-07-02\n"
            "updated: 2026-07-02\nvalid_from: 2026-07-02\ntags: []\n---\n\n"
            "Iets dat nog niet beoordeeld is.\n", encoding="utf-8")

    def _export(self):
        return self.m.export(self.vault, self.out)

    def _fm_of(self, rel):
        text = (self.out / rel).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), rel)
        fm_text = text.split("---\n", 2)[1]
        if HAVE_YAML:
            return yaml.safe_load(fm_text) or {}
        from _frontmatter import parse_frontmatter
        fm, _ = parse_frontmatter(text)
        return fm

    # --- par. 11 conformantie ---

    def test_every_concept_has_nonempty_type(self):
        r = self._export()
        self.assertEqual(r["written"], 4)
        for f in self.out.rglob("*.md"):
            if f.name in ("index.md", "log.md"):
                continue
            fm = self._fm_of(f.relative_to(self.out).as_posix())
            self.assertTrue(str(fm.get("type", "")).strip(),
                            f"leeg type in {f}")

    def test_directory_indexes_and_root_version(self):
        self._export()
        root_index = (self.out / "index.md").read_text(encoding="utf-8")
        self.assertIn('okf_version: "0.2"', root_index)
        sub_index = (self.out / "02-wiki" / "index.md").read_text(encoding="utf-8")
        self.assertFalse(sub_index.startswith("---"),
                         "alleen de root-index mag frontmatter dragen (par. 8)")
        self.assertIn("* [", sub_index)

    def test_wikilinks_become_absolute_markdown_links(self):
        r = self._export()
        body = (self.out / "02-wiki" / "wireguard.md").read_text(encoding="utf-8")
        self.assertIn("[de proxy](/02-wiki/traefik.md)", body)
        self.assertNotIn("[[traefik", body)
        # onbekend target: wel een markdown-link, wel geteld
        self.assertIn("[onbekend-artikel](/onbekend-artikel.md)", body)
        self.assertGreaterEqual(r["broken_links"], 1)

    # --- trust-tier-mapping ---

    def test_unverified_maps_to_draft_without_verified(self):
        self._export()
        fm = self._fm_of("09-memory/2026-07-02-open.md")
        self.assertEqual(fm.get("status"), "draft")
        self.assertNotIn("verified", fm)

    def test_current_maps_to_machine_confirmed(self):
        if not HAVE_YAML:
            self.skipTest("PyYAML vereist: geneste frontmatter-asserties")
        self._export()
        fm = self._fm_of("09-memory/2026-07-01-besluit.md")
        self.assertNotIn("status", fm)  # stable = spec-default, niet dubbel
        v = fm.get("verified")
        self.assertIsNotNone(v)
        entry = v[0] if isinstance(v, list) else v
        self.assertTrue(str(entry["by"]).startswith("process:"))

    def test_human_approval_from_review_log_adds_human_tier(self):
        if not HAVE_YAML:
            self.skipTest("PyYAML vereist: geneste frontmatter-asserties")
        (self.vault / ".claude" / "memory-review-log.jsonl").write_text(
            json.dumps({"ts": "2026-07-03T10:00:00+00:00",
                        "stem": "2026-07-01-besluit", "decision": "approve",
                        "new_status": "current", "via": "command"}) + "\n",
            encoding="utf-8")
        self._export()
        fm = self._fm_of("09-memory/2026-07-01-besluit.md")
        v = fm.get("verified")
        self.assertIsInstance(v, list)
        bys = [str(e["by"]) for e in v]
        self.assertTrue(any(b.startswith("process:") for b in bys))
        self.assertTrue(any(b.startswith("human:") for b in bys))

    def test_generated_carries_producer_provenance(self):
        if not HAVE_YAML:
            self.skipTest("PyYAML vereist: geneste frontmatter-asserties")
        self._export()
        fm = self._fm_of("09-memory/2026-07-01-besluit.md")
        gen = fm.get("generated")
        self.assertIsNotNone(gen)
        self.assertIn("ollama/qwen3:8b", str(gen["by"]))
        self.assertIn("p1", str(gen["by"]))

    def test_sources_from_provenance(self):
        if not HAVE_YAML:
            self.skipTest("PyYAML vereist: geneste frontmatter-asserties")
        self._export()
        fm = self._fm_of("02-wiki/wireguard.md")
        srcs = fm.get("sources")
        self.assertTrue(srcs)
        self.assertEqual(srcs[0]["id"], "raw-sessie-2026-07-01-vpn")
        self.assertEqual(srcs[0]["resource"], "/01-raw/sessies/raw-sessie-2026-07-01-vpn.md")

    # --- idempotentie ---

    def test_two_exports_byte_identical(self):
        self._export()
        snap1 = {f.relative_to(self.out).as_posix(): f.read_bytes()
                 for f in self.out.rglob("*.md")}
        self._export()
        snap2 = {f.relative_to(self.out).as_posix(): f.read_bytes()
                 for f in self.out.rglob("*.md")}
        self.assertEqual(snap1, snap2)

    def test_empty_vault_reports_empty(self):
        empty = Path(self.tmp.name) / "leeg"
        empty.mkdir()
        r = self.m.export(empty, Path(self.tmp.name) / "leeg-out")
        self.assertTrue(r["empty"])


if __name__ == "__main__":
    unittest.main()
