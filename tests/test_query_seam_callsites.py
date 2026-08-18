"""Every query-side embed flows through _embeddings.embed_query (TASK-184).

Before the seam existed, the eval family embedded queries with kind="query"
while every production path embedded bare: the moment a query prefix gets
configured, kb-eval — which claims production parity — would measure a
different retrieval system than the live hook runs, silently. This guard
makes a bare `embed(` call in a query-bearing file a test failure.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Files that embed user/eval queries. A new query surface belongs here.
QUERY_FILES = [
    "scripts/kb-retrieve.py",
    "scripts/kb-search.py",
    "scripts/kb-presearch.py",
    "scripts/kb-mcp.py",
    "scripts/kb-ask.py",
    "scripts/kb-eval.py",
    "scripts/rerank-eval.py",
    "scripts/recall-ablation.py",
    "scripts/rank-factors.py",
    "scripts/rerank-ceiling.py",
    "scripts/find-similar.py",
    "scripts/_groundcheck.py",
    "atlas/sidecar/sources.py",
]

#: Bare embed( calls that are legitimately not queries.
ALLOWED = (
    'kind="doc"',        # document-side embeds (e.g. _groundcheck windows)
    '"ping"', '"warm"', '"dimensie-probe"',  # health and dimension probes
    'emb.embed)(query)',  # the sidecar's getattr deploy-skew fallback
)

_BARE_EMBED = re.compile(r"\bembed\(")


class QuerySeamGuardTest(unittest.TestCase):
    def test_every_query_path_goes_through_the_seam(self):
        offenders = []
        for rel in QUERY_FILES:
            text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
            self.assertIn("embed_query", text,
                          f"{rel} has no embed_query call at all")
            for m in _BARE_EMBED.finditer(text):
                # the call plus a little context; enough to see kind= or probe
                snippet = text[m.start():m.start() + 80]
                around = text[max(0, m.start() - 40):m.start() + 80]
                if any(a in around for a in ALLOWED):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{rel}:{line} {snippet.splitlines()[0]}")
        self.assertEqual(
            offenders, [],
            "bare embed() on a query path; use _embeddings.embed_query: "
            + "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
