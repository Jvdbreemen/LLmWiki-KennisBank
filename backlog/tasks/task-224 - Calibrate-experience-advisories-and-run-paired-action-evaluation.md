---
id: TASK-224
title: Calibrate experience advisories and run paired action evaluation
status: In Progress
assignee: []
created_date: '2026-08-29 00:00'
labels:
  - experience-memory
  - evaluation
  - safety
  - human-review
dependencies:
  - TASK-219
  - TASK-220
ordinal: 176300
---

## Description

Create an independent advisory-development set, calibrate the failure-warning
gate there, and rerun the frozen reviewed holdout without further tuning. Also
human-review the provisional success/failure/mixed/partial labels and compare
correct action selection with and without retrieved experience.

The current retrieval gain is not permission to tune the ten reviewed negative
probes. They have already produced a measured 0.20 false-warning rate and must
remain untouched until the final rerun.

## Acceptance Criteria

- [x] #1 A separate labelled development set contains failure matches and unrelated/no-warning probes
- [x] #2 Threshold and routing changes are selected using only the development set and committed before the holdout rerun
- [x] #3 A human confirms or corrects all 60 provisional outcome-state labels
- [ ] #4 The untouched holdout false-warning rate is at most 0.10 and advisory precision at least 0.90
- [ ] #5 Validated failure hit@3 remains at least 0.70 with evidence precision 1.00 and zero candidate leakage
- [ ] #6 At least 60 paired action judgments report delta and confidence interval against the strongest baseline
- [ ] #7 No threshold is accepted if the gain is explainable by lexical retrieval alone
- [ ] #8 Skill promotion and outcome-aware ranking remain disabled unless every gate passes and the owner approves

## Evidence baseline

The completed human review separates attempt state, resolution state, and the
evaluator-facing final state for all 60 cases. Final states contain 38 success,
18 partial, 1 mixed, and 3 failure episodes; the independent attempt axis still
preserves 29 failures for dead-end recall.

The frozen-holdout rerun measured hybrid hit@3 0.90 versus lexical 0.80,
failure hit@3 0.667, p95 133.0 ms, evidence precision 1.00, and candidate
leakage zero. One of ten abstention probes received a warning, meeting the 0.10
boundary, but advisory precision is only 0.667 and one of three final failures
was missed. Rollout remains rejected until this task supplies independent
calibration and paired value evidence.

## Protocol amendment before the next frozen rerun

The two-axis review exposed a defect in that baseline: the advisory evaluator
treated only a final `failure` as a failed approach. A repaired episode such as
`failure -> fix_validated -> success` is exactly where recall can prevent a
repeated dead end, so classifying its warning as incorrect erases the lesson.

The implementation and evaluator now preserve `attempt_state`,
`resolution_state`, and final `outcome_state` separately. Failure retrieval and
advisory correctness use the attempt axis; final-state calibration continues to
use `outcome_state`. Legacy records with no attempt label fall back only when
their final state is failure. This semantic correction is committed and tested
before further threshold selection or another frozen-holdout run. The 0.667
failure/advisory figures above remain historical baseline evidence, not the
target for development-set tuning.

## Independent development calibration

The owner-reviewed development set contains 11 positive failed-approach cases
and 10 factual no-warning probes over 21 unique sources. Its IDs, exact queries,
and evidence sources are disjoint from the 60-case frozen source holdout. The
private cases and per-query observations remain outside the repository.

On `ollama:qwen3-embedding:4b`, the selected threshold is 0.50: positive recall
10/11 (0.909), precision 10/11 (0.909), and one false warning in ten negatives
(0.10). Pure lexical retrieval reaches 8/11 positive recall and returns a
warning for all ten negatives, so the hybrid gain is 2/11 (18.2 percentage
points) and is not explained by lexical matching. Threshold 0.45 violates the
safety gates; 0.55 removes false warnings but drops positive recall to 7/11.

The incumbent numeric default was already 0.50. It is now versioned as
`FAILURE_ADVISORY_MIN_COS`, the gateway reads that constant, and
`scripts/calibrate-experience-advisory.py` reproduces the private calibration
without writing prompts to the repository. Aggregate evidence is recorded in
`docs/research/experience-advisory-calibration-2026-08-30.md`. The frozen
holdout has not been rerun after this selection.
