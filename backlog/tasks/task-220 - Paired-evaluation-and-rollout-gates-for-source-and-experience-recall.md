---
id: TASK-220
title: Build paired evaluation and rollout gates for source and experience recall
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-29 00:00'
labels:
  - evaluation
  - source-recall
  - experience-memory
  - regression
dependencies:
  - TASK-212
  - TASK-213
  - TASK-215
  - TASK-216
  - TASK-218
  - TASK-219
ordinal: 175900
---

## Description

Create the evaluation harness that decides whether the two new paths deliver
real value. Phase A (this preregistration and its contract tests) must be
complete before feature implementation. Phase B runs only after the candidate
layers exist and produces the versioned evidence packet. Do not rely on a
single aggregate recall score. Evaluate source
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

Retrieval metrics are necessary but insufficient: the final packet must also
compare answer correctness for source recall and correct action selection for
experience recall against the strongest non-experimental baseline. A positive
retrieval result without a paired downstream improvement is a hold or reject,
not a rollout approval.

The research arm F must not be enabled by default. It exists to determine
whether outcome-aware ranking is better than simple gated recall.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The harness evaluates all six arms or records a justified reason for an omitted arm
- [x] #2 Source metrics include source hit@k, exact passage/provenance correctness, not-found precision, and conflict handling
- [x] #3 Experience metrics include useful reuse, repeated-failure rate, false warnings, unsupported lessons, and outcome calibration
- [x] #4 Existing wiki/memory recall@k and normal-path latency have regression gates
- [x] #5 Normal, source, and experience paths report separate p50/p95 latency and failure-open behaviour
- [x] #6 A pre-registered decision table defines go, hold, and reject thresholds before production routing changes
- [x] #7 The report states whether outcome-aware ranking is justified; a non-significant or noisy result keeps ranking unchanged
- [x] #8 Evaluation runs do not write production usage/outcome telemetry or mutate the vault
<!-- AC:END -->

## Evidence

- `scripts/_layer_eval.py` contains the fixed six-arm coverage check,
  nearest-rank latency summaries, separate source/experience gates, and the
  preregistered `go`/`hold`/`reject` decision table.
- `scripts/_layer_eval_runner.py` reports source conflicts, provenance,
  useful reuse, repeated-failure reuse, unsupported lessons, false warnings,
  and outcome calibration without retaining prompts.
- `scripts/kb-layer-eval.py` writes only an aggregate evidence packet and
  forces `KB_USAGE_DISABLE=1` during report construction.
- Focused evidence: 16 evaluator, runner, and packet tests pass.
- `docs/research/source-experience-evidence-packet-2026-08-26.md` records the
  current content-safe decision: source **hold**, experience **hold**, and
  outcome-aware ranking **reject for this release**. The report includes the
  live corpus/oracle limitations and does not turn smoke-test retrieval into a
  usefulness claim.

`docs/research/source-experience-evidence-packet-2026-08-29.md` records the
reviewed live result: source **hold**, experience **reject for rollout**, and
outcome-aware ranking **reject**. The harness now distinguishes missing paired
answer/action samples from measured zero benefit, gives measured safety failures
precedence over missing downstream labels, and tolerates floating-point noise
at the exact ten-point gain boundary. No rollout is authorized.

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Use the existing eval discipline and preserve frozen baselines. The L2 scene
experiment is evidence that a derived layer must show an oracle ceiling and a
net gain before it is admitted to retrieval.
<!-- SECTION:NOTES:END -->
