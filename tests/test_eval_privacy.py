"""Privacy-guard: persoonlijke eval-sets horen NOOIT in repo of release.

De echte sets (<vault>/06-claude/*.json) zijn afgeleid van prive
vault-inhoud (artikel- en memory-titels). Alleen de verzonnen
*.example.json-varianten mogen getrackt zijn. Eigenaarsdirectief 2026-07-29:
"de eval suite mag niet online in de release zitten — die moet altijd prive
blijven."
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FORBIDDEN_NAMES = {"kb-eval-set.json", "kb-memory-eval-set.json",
                   "kb-activity-eval-set.json"}


def _tracked() -> list:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout
    return out.splitlines()


class EvalPrivacyTest(unittest.TestCase):
    def test_no_live_eval_sets_tracked(self):
        offenders = [f for f in _tracked()
                     if Path(f).name in FORBIDDEN_NAMES]
        self.assertEqual(offenders, [],
                         "persoonlijke eval-set getrackt in git — die moet prive blijven")

    def test_no_draft_sets_tracked(self):
        offenders = [f for f in _tracked() if f.endswith(".draft.json")]
        self.assertEqual(offenders, [],
                         "eval-drafts getrackt in git — die komen uit de prive vault")

    def test_no_vault_06_claude_paths_tracked(self):
        offenders = [f for f in _tracked() if "06-claude/" in f.replace("\\", "/")]
        self.assertEqual(offenders, [],
                         "06-claude-vaultpad getrackt in git")

    def test_example_sets_stay_small_and_fabricated(self):
        """Een bulk-paste van echte vragen in een example-bestand is de
        sluiproute; example-sets horen documentatie-formaat te blijven."""
        import json
        for name in ("kb-eval-set.example.json", "kb-memory-eval-set.example.json"):
            p = REPO / name
            if not p.exists():
                continue
            entries = json.loads(p.read_text(encoding="utf-8"))
            self.assertLessEqual(
                len(entries), 25,
                f"{name} bevat {len(entries)} entries — example-sets blijven klein; "
                "echte sets leven uitsluitend in de vault")


if __name__ == "__main__":
    unittest.main()
