---
id: TASK-220
title: Build paired evaluation and rollout gates for source and experience recall
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - evaluation
  - source-recall
  - experience-memory
  - regression
dependencies:
  - TASK-213
  - TASK-215
  - TASK-216
  - TASK-218
  - TASK-219
ordinal: 175900
---

## Description

Create the evaluation harness that decides whether the two new paths deliver
real value. Do not rely on a single aggregate recall score. Evaluate source
evidence, memory regressions, experience reuse, failure prevention, attribution
quality, latency, and false warnings separately.

Compare at least these arms:

    A  current wiki + memory
    B  A + explicit source recall
    C  A + gated source fallback
    D  A + experience recall
    E  A + source recall + experience recall
    F  E + outcome-aware routing/ranking (research arm only)

Use fixed golden and holdout sets. Keep questions generated from the new
system out of the baseline set. Include source-only, temporal, supersession,
narrowing, success, failure, and unknown cases.

The research arm F must not be enabled by default. It exists to determine
whether outcome-aware ranking is better than simple gated recall.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The harness evaluates all six arms or records a justified reason for an omitted arm
- [ ] #2 Source metrics include source hit@k, exact passage/provenance correctness, not-found precision, and conflict handling
- [ ] #3 Experience metrics include useful reuse, repeated-failure rate, false warnings, unsupported lessons, and outcome calibration
- [ ] #4 Existing wiki/memory recall@k and normal-path latency have regression gates
- [ ] #5 Normal, source, and experience paths report separate p50/p95 latency and failure-open behaviour
- [ ] #6 A pre-registered decision table defines go, hold, and reject thresholds before production routing changes
- [ ] #7 The report states whether outcome-aware ranking is justified; a non-significant or noisy result keeps ranking unchanged
- [ ] #8 Evaluation runs do not write production usage/outcome telemetry or mutate the vault
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Use the existing eval discipline and preserve frozen baselines. The L2 scene
experiment is evidence that a derived layer must show an oracle ceiling and a
net gain before it is admitted to retrieval.
<!-- SECTION:NOTES:END -->

