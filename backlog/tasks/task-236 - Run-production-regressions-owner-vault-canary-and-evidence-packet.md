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
- [x] #9 Full repository suite and every supported client smoke are green

## Evidence

Publish a sanitized aggregate packet under `docs/research/`; keep per-case
private material inside the configured vault.

Current aggregate packet:
`docs/research/production-recall-canary-evidence-2026-09-07.md`. The source
canary passes 10/10. Experience remains a documented hold at 0/20 naturally
occurring explicit reviews; no eval projection was promoted into the canonical
owner ledger.

Shadow-capture audit (2026-09-07): the session outcome recorder was found to
target the retired mixed store and ignore the new capture flag. It now appends
idempotent events/outcomes to the canonical ledger under same-vault policy.
The new source-first capture CLI creates exact SourceRefs before append and
cannot write the projection. A synthetic capture/outcome/review/rebuild proof
passed, as did 236 focused regressions (one existing Windows symlink skip) and
a real temporary setup deployment. This is mechanism evidence only; criterion
#7 remains 0/20 and no production-value claim was upgraded.

Static current-commit proof: commit `468acd1` ran the complete Python repository
suite in isolation with `1991 passed, 4 skipped` in 857.54 seconds. The four
skips are existing platform/optional-capability skips, not failures. The suite
includes the cross-client install, generated-artifact, MCP-wire, and setup
smokes; the unchanged Atlas frontend had separately passed typecheck and 39/39
tests earlier in this branch cycle.

Owner-vault shadow activation: the capture cohort was deployed from clean
feature commit `468acd1` after timestamped backup. Only
`experience_capture=true`; projection and both explicit read flags remain off.
Disabled and enabled-invalid smokes created no ledger, so no synthetic case was
counted. A default projection doctor was stopped after five minutes while
hashing the 16,318-file (~0.82 GiB) source corpus; this incomplete run is not
reported as green. TASK-238 added an honest `--fast` mode: the same owner-vault
routine check completed read-only in 546.8 ms while marking expensive inventory,
source integrity, chunk, and exact-ref checks `not_checked`/null.
