---
id: TASK-176
title: Verify OKF interop with Memanto, the format's second implementation
status: To Do
assignee: []
created_date: '2026-08-15 21:50'
updated_date: '2026-08-15 21:50'
labels: []
dependencies: ['TASK-92']
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Memanto evaluation (docs/research/agent-memory-field-review-and-strategy.md,
follow-up section). Depends on TASK-92 (the OKF v0.2 export) being merged.

Memanto (github.com/moorcheh-ai/memanto, MIT, ~1.8k stars, arXiv 2604.22085)
exports its memory estate "as plain Markdown in the Open Knowledge Format
(OKF), a portable interchange format intentionally supporting competitor
implementations" — the same GoogleCloudPlatform/knowledge-catalog v0.2 spec
TASK-92 adopted. OKF now has at least two independent serious implementations,
which changes what TASK-92's export is: no longer only a rendered view, but an
interchange surface another ecosystem actually reads and writes.

Two checks, both cheap and both off the hot path:

1. **Outbound**: a `kb-okf-export.py` bundle from a test vault validates against
   whatever conformance tooling Memanto or the spec repo ships, and a Memanto
   instance (local Docker + Ollama mode — no cloud) can ingest it without
   losing the trust tiers TASK-92 mapped (unverified/draft, process-verified,
   human-verified, deprecated).
2. **Inbound, exploratory only**: what a Memanto OKF estate looks like against
   KennisBank's frontmatter contract — which of their 13 memory categories map
   onto feit/voorkeur/procedure/beslissing, and which have no home (goal,
   instruction, relationship). NOT an importer; a mapping table and a gap list.
   An import path is a separate decision that needs an owner use case first.

Divergences belong in the report, not silently patched: where the two
implementations read the spec differently, that is a finding about the young
spec (v0.2, Google-steered — the risk TASK-92 already recorded) and possibly an
upstream issue worth filing on knowledge-catalog.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An exported bundle from a test vault is ingested by a local (Docker+Ollama, no cloud) Memanto without error; what survives and what is dropped is recorded
- [ ] #2 The trust-tier mapping survives the round trip or the loss is documented per tier
- [ ] #3 A mapping table: Memanto's 13 categories against the vault's 4 memory types, with the unmappable ones named
- [ ] #4 Spec-reading divergences between the two implementations are written down; upstream issues filed where the spec is ambiguous
- [ ] #5 No import path is built; that remains a separate owner decision
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
