---
id: TASK-244
title: Run independent automated experience evaluation before owner pilot
status: Done
assignee: []
created_date: '2026-09-09 17:40'
updated_date: '2026-09-09 17:44'
labels:
  - evaluation
  - experience
  - pilot
dependencies: []
ordinal: 183600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Evaluate the production experience route without owner interaction using a fresh, private, source-grounded replay set or an independent held-out set. Keep spent holdouts and natural owner-canary evidence separate. Measure retrieval, provenance, abstention, latency, leakage, and paired action correctness where labels are available. Use automated checks as pre-pilot evidence, but do not relabel model judgments as natural owner usefulness or harm.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The input set is new or explicitly marked as a regression replay; no spent holdout is used for tuning
- [x] #2 The run is read-only against the owner vault and stores only aggregate content-safe evidence in the repository
- [x] #3 Retrieval, provenance, leakage, latency and abstention metrics are reported with pass/fail gates
- [x] #4 The report explicitly separates automated evidence from owner-reviewed natural-use evidence
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Freeze the regression-replay protocol before running. 2. Test the evaluation harness before implementation. 3. Run retrieval/provenance/leakage/latency/abstention checks in an isolated projection and independently rescore the existing blinded action judgments. 4. Publish aggregate evidence and concrete failures without requiring any new owner labels. Keep natural-use claims separate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Initial data audit 2026-09-09: owner ledger contains 60 experience events, 60 outcomes and 1 accepted review; outcome states are 29 mixed, 24 failure, 6 unknown, 1 success. This supports a read-only corpus/coverage audit, but not automatic promotion of 59 unreviewed experiences. Automated evaluation must report retrieval/provenance/abstention/latency separately from subjective owner usefulness and harm.

Completed independently on 2026-09-09. Evidence:
`docs/research/automated-experience-regression-evidence-2026-09-09.md`.
Actual current-gateway replay: hybrid 42/60 versus lexical 37/60; 13 mixed
wiki/raw evidence bundles conservatively excluded; negative no-hit 0/10;
892/892 shown reference resolutions valid; 22/22 safety controls pass. Hybrid
p95 initially 515 ms under concurrent load, then 183/142/167 ms in three
diagnostic repeats with unchanged rankings. Historical action rescore remains
43/60 versus 19/60; it is not a new answer-generation result. Frozen inputs
unchanged; no owner data/review/flag mutation. Final owner snapshot is 62 events,
62 outcomes, one review and one eligible experience. TASK-245 now tracks the
measured release gaps instead of duplicating this evaluation task. Done means
the evaluation is complete, not that its failed release gates passed.

Final focused verification: 64 passed, one existing Windows symlink privilege
skip, no failures/errors in 19.39s. Final JUnit SHA256:
94e5dd6a5b4a05e8c65b73847292ffe56e50c8d1c9b00f97096edb94e60a0099.
Harness source hash is unchanged from the actual 70-case run. Four additional
evaluation-isolation tests were added after the run; an intermediate test-only
SQLite cleanup failure and its corrected rerun are both preserved in the report.
<!-- SECTION:NOTES:END -->
