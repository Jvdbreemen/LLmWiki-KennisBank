---
id: TASK-236
title: Run production regressions, owner-vault canary, and evidence packet
status: In Progress
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - evaluation
  - canary
  - performance
  - evidence
dependencies:
  - TASK-232
  - TASK-234
  - TASK-235
ordinal: 177500
---

## Description

Prove implementation integrity and practical explicit-use value without
recycling spent holdouts as fresh science. Run locked regressions, full tests,
performance/privacy/failure checks, then stage the flags through shadow capture,
shadow projection, source canary, and experience canary in the configured
owner vault.

## Acceptance Criteria

- [ ] #1 Provenance is 100% on all shown canary passages and candidate leakage is zero
- [x] #2 Locked experience regression reaches hit@3 >= 0.85 and evidence precision 1.00 with no tuning on those cases
- [x] #3 Normal recall remains byte/shape compatible with <= 1 ms extra p95 overhead
- [x] #4 Warm experience p95 <= 250 ms, source FTS p95 <= 250 ms, and exact hydration p95 <= 50 ms
- [x] #5 Failure injection proves fail-open behavior and previous-good-index recovery
- [x] #6 At least ten exact source reconstructions are owner-checked before experience canary begins
- [ ] #7 At least twenty naturally occurring explicit experience recalls are reviewed; >= 70% useful, <= 5% harmful, and 100% evidence-correct
- [x] #8 Aggregate report contains no private prompts/passages and distinguishes prior evidence, regression evidence, and new canary evidence
- [ ] #9 Full repository suite and every supported client smoke are green

## Evidence

Publish a sanitized aggregate packet under `docs/research/`; keep per-case
private material inside the configured vault.

Current aggregate packet:
`docs/research/production-recall-canary-evidence-2026-09-07.md`. The source
canary passes 10/10. Experience remains a documented hold at 0/20 naturally
occurring explicit reviews; no eval projection was promoted into the canonical
owner ledger.
