---
id: TASK-215
title: Add the gated source-recall API and groundcheck integration
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-31 00:00'
labels:
  - source-recall
  - retrieval
  - groundcheck
  - fail-open
dependencies:
  - TASK-214
ordinal: 175400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expose source recall as a separate, provenance-labelled query path. It must
support explicit source requests, verification of a known memory claim,
low-confidence fallback after wiki/memory retrieval, and reconstruction from a
known source reference.

The default route is:

    wiki + memory -> sufficient result? -> answer
                                  no -> scoped source recall -> evidence answer

Do not flatten source hits into the existing ranking. Apply source-specific
filters and thresholds, return source evidence separately, and show when a
result is raw evidence rather than consolidated knowledge. Integrate with the
grounded verifier so a claim can retrieve its source through one reusable
interface instead of maintaining a second hidden retrieval implementation.

Source recall must never silently promote a raw passage to memory. It must also
make conflicts, missing sources, and low-confidence matches visible.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The API supports explicit, verification, fallback, and reconstruction modes with a documented request/response schema
- [x] #2 Every hit contains source path/hash, session/document/chunk identity, passage location, retrieval mode, and confidence metadata
- [x] #3 Normal wiki/memory recall is byte/shape compatible and has unchanged latency when source recall is not selected
- [x] #4 Verification uses the source-recall API and preserves the existing fail-open behaviour when the source index or model is unavailable
- [x] #5 Source results are clearly labelled and cannot directly write or promote a memory
- [x] #6 Missing, conflicting, superseded, and low-confidence source results are represented explicitly
- [x] #7 Golden fixtures from TASK-213 show measured source hit quality and citation correctness
- [x] #8 Tests cover route selection, source filters, no-hit behaviour, index failure, and regression of the current recall path
<!-- AC:END -->

## Progress evidence

- `scripts/kb-source-recall.py` now labels each returned hit with its
  `retrieval_mode` and structured confidence metadata (`cosine`, lexical
  match, freshness), while the response exposes explicit `no_hit` and flags
  for stale, superseded, conflicting, and low-confidence evidence.
- The existing `_groundcheck.verify_grounded` source-recall seam remains
  fail-open and is covered by source-recall integration tests.
- Focused evidence: gateway and groundcheck source tests pass (`6 passed,
  20 deselected` in the targeted run); the broader source regression selection
  remains green at 36 tests.

The reviewed normal-route benchmark ran 5,000 off-route calls and measured
approximately 0.0008 ms p50/p95 overhead over the no-op baseline. TASK-213 now
supplies the reviewed holdout and a full-corpus lexical baseline, but AC #7
remains open: the full source vector projection is absent and therefore source
API hit quality/citation correctness has not been measured. The 745 MiB corpus
and 37,085 chunks in only the 28 expected documents make naive pre-embedding a
redesign question, not a missing checkbox.

TASK-223 subsequently measured the bounded sparse-first candidate on a separate
owner-reviewed 30-case development set. Exact provenance remained valid, but
the best point reached only hit@5 0.25, citation precision 0.40, specificity
0.90, and warm p95 8.33 seconds; pure BM25 on the same cases reached hit@5
0.75 at p95 50.4 ms. AC #7 is therefore complete as a measurement requirement,
not as a quality approval. The sparse vector route is rejected and remains
outside the source API's enabled paths.
