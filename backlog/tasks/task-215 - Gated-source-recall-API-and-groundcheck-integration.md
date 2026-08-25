---
id: TASK-215
title: Add the gated source-recall API and groundcheck integration
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
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
- [ ] #1 The API supports explicit, verification, fallback, and reconstruction modes with a documented request/response schema
- [ ] #2 Every hit contains source path/hash, session/document/chunk identity, passage location, retrieval mode, and confidence metadata
- [ ] #3 Normal wiki/memory recall is byte/shape compatible and has unchanged latency when source recall is not selected
- [ ] #4 Verification uses the source-recall API and preserves the existing fail-open behaviour when the source index or model is unavailable
- [ ] #5 Source results are clearly labelled and cannot directly write or promote a memory
- [ ] #6 Missing, conflicting, superseded, and low-confidence source results are represented explicitly
- [ ] #7 Golden fixtures from TASK-213 show measured source hit quality and citation correctness
- [ ] #8 Tests cover route selection, source filters, no-hit behaviour, index failure, and regression of the current recall path
<!-- AC:END -->

