---
id: TASK-224
title: Calibrate experience advisories and run paired action evaluation
status: To Do
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

- [ ] #1 A separate labelled development set contains failure matches and unrelated/no-warning probes
- [ ] #2 Threshold and routing changes are selected using only the development set and committed before the holdout rerun
- [ ] #3 A human confirms or corrects all 60 provisional outcome-state labels
- [ ] #4 The untouched holdout false-warning rate is at most 0.10 and advisory precision at least 0.90
- [ ] #5 Validated failure hit@3 remains at least 0.70 with evidence precision 1.00 and zero candidate leakage
- [ ] #6 At least 60 paired action judgments report delta and confidence interval against the strongest baseline
- [ ] #7 No threshold is accepted if the gain is explainable by lexical retrieval alone
- [ ] #8 Skill promotion and outcome-aware ranking remain disabled unless every gate passes and the owner approves

## Evidence baseline

The reviewed projection measured hybrid hit@3 0.90 versus lexical 0.80,
failure hit@3 0.864, p95 105.6 ms, evidence precision 1.00, and candidate
leakage zero. Two of ten abstention probes still received warnings, so rollout
is rejected until this task supplies independent calibration and paired value
evidence.
