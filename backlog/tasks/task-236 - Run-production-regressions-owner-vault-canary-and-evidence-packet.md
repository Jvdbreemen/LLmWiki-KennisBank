---
id: TASK-236
title: 'Run production regressions, owner-vault canary, and evidence packet'
status: In Progress
assignee: []
created_date: '2026-09-04 00:00'
updated_date: '2026-09-08 05:54'
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

<!-- SECTION:DESCRIPTION:BEGIN -->
Prove implementation integrity and practical explicit-use value without
recycling spent holdouts as fresh science. Run locked regressions, full tests,
performance/privacy/failure checks, then stage the flags through shadow capture,
shadow projection, source canary, and experience canary in the configured
owner vault.

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

Live corpus preparation (2026-09-07): shadow capture had accumulated 33 events
and 33 outcomes. A private dry run verified seven exact raw-source references;
one task-scoped candidate/outcome was appended without changing existing rows
or adding a review. Replay produced no duplicate. Post-append quick integrity
passed with 34 events, 34 outcomes, zero reviews, no projection, and read routes
disabled. Focused capture/review/extraction/canary tests: 30 passed in 2.70s.
The private pending-review packet awaits the owner's explicit decision. This
is retrospective corpus preparation, not a natural recall: criterion #7 stays
0/20. Criterion #9 evidence remains bound to 468acd1; the later full run's final
result was not recovered and current-HEAD full-suite proof remains a release
prerequisite. No main merge or release was performed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 Provenance is 100% on all shown canary passages and candidate leakage is zero
- [x] #2 #2 Locked experience regression reaches hit@3 >= 0.85 and evidence precision 1.00 with no tuning on those cases
- [x] #3 #3 Normal recall remains byte/shape compatible with <= 1 ms extra p95 overhead
- [x] #4 #4 Warm experience p95 <= 250 ms, source FTS p95 <= 250 ms, and exact hydration p95 <= 50 ms
- [x] #5 #5 Failure injection proves fail-open behavior and previous-good-index recovery
- [x] #6 #6 At least ten exact source reconstructions are owner-checked before experience canary begins
- [ ] #7 #7 At least twenty naturally occurring explicit experience recalls are reviewed; >= 70% useful, <= 5% harmful, and 100% evidence-correct
- [x] #8 #8 Aggregate report contains no private prompts/passages and distinguishes prior evidence, regression evidence, and new canary evidence
- [ ] #9 #9 Full repository suite and every supported client smoke are green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-08: reopening current-HEAD full-suite proof explicitly; prior 468acd1 evidence remains historical. New projection capability bypass must be repaired before production acceptance.

2026-09-08 shadow projection: owner explicitly accepted one bounded lesson; all seven SourceRefs revalidated and review bound to unchanged content hash. New gated CLI returned disabled before opt-in, then built one lexical record and excluded 40 unreviewed candidates. Ledger snapshot 41 events/41 outcomes/1 review; both read routes remain disabled. This is mechanism/corpus proof, not natural recall; canary remains 0/20. Details: docs/research/projection-build-capability-evidence-2026-09-08.md.

Clean 8c323a0 full suite completed: 2018 passed, 4 skipped, 1 failed in 636.13s; JUnit persisted and hashed. Sole failure was TASK-209 test discovery, now repaired with TestCase methods and verified under both runners. During deployment preflight, TASK-241 also reproduced and repaired the actual shell doctor using retired flags/schema and unbounded inventory. AC9 remains unchecked until a new clean-commit full run passes. No new natural experience recall is claimed.
<!-- SECTION:NOTES:END -->
