"""English-by-default guard over translated surfaces (TASK-192).

Deliberately a RATCHET, not a blanket: 70 of 101 scripts still contain Dutch,
and the full-translation programme (TASK-157: 188 files, 1245 comments, 611
strings, 6 prompts needing re-measurement) was dropped on the owner's request
on 2026-08-13. This guard covers everything under .github/ (new workflows
included, automatically) plus each script as it gets translated — append to
ENGLISH_ONLY when you translate one, and the debt cannot regrow there.

Vault data-format literals (``raw-sessie-``, the ``## Sessie-herkomst``
heading, ``05-bronnen/`` paths) are the Dutch vault's schema, not prose; the
word list is curated so they never match.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

ENGLISH_ONLY = sorted(
    str(p.relative_to(REPO)).replace("\\", "/")
    for p in (REPO / ".github").rglob("*")
    if p.is_file() and p.suffix in (".yml", ".yaml", ".md")
) + [
    "scripts/kb-lint.py",
]

#: Dutch function words that do not occur in English prose or in the kept
#: vault literals. Curated, not exhaustive — enough that any Dutch sentence
#: trips at least one.
DUTCH_WORDS = re.compile(
    r"\b(geen|niet|wordt|worden|zodat|waarvan|omdat|bewust|zoals|deze|"
    r"hierdoor|daarom|altijd|nooit|moeten|hoort|tegen|tussen)\b")


class LanguagePolicyTest(unittest.TestCase):
    def test_translated_surfaces_stay_english(self):
        offenders = []
        for rel in ENGLISH_ONLY:
            path = REPO / rel
            if not path.exists():
                continue
            for i, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if DUTCH_WORDS.search(line):
                    offenders.append(f"{rel}:{i}: {line.strip()[:80]}")
        self.assertEqual(
            offenders, [],
            "Dutch text on a translated surface (repo policy: English by "
            "default):\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
