---
id: TASK-129
title: Ablate the seven ranking factors and delete what does not earn its place
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 11:00'
labels: []
dependencies: []
ordinal: 102400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).
This is a removal task and it gates the rest of the memory roadmap.

`_rank.py` multiplies seven signals on the memory layer: relevance (hybrid RRF)
x recency (per-type half-life + floor) x importance (judge 1-5) x trust
(evidence_basis) x usage (1.10/1.05) x noise (up to -20%, floor 0.80) x coupling
(1.05/1.10), plus graph-neighbour expansion on top. Each was introduced with its
own justification and measured only by whether the total moved recall@k.

Collectively they are unattributable. A 1.05 boost and a 0.80 floor interact in
ways nobody can reason about, a regression cannot be traced to a factor, and
every added signal makes the next one harder to evaluate. This is the "drie
clevere mechanismen" KISS warns against, reached one reasonable step at a time.

Turn each factor off individually against the frozen eval set, record the delta,
and delete any whose contribution is indistinguishable from noise. Expect at
least one deletion: a 1.05 factor inside a seven-way product is plausibly below
the measurement floor.

The harness exists — TASK-86 (frozen eval runs, parity with the hook) and
TASK-72 (observed rank as selection criterion). No new measurement machinery
should be needed; if it is, that is itself a finding.

Standing consequence: no new ranking factor joins the product without passing
this same bar, including the outcome signal from TASK-132.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Per-factor ablation against the frozen memory eval set: each of the seven off individually, delta in recall@1/@3/@5 and MRR recorded
- [ ] #2 The measurement method and the full result table are written down, including factors that stayed
- [ ] #3 Every factor whose delta is indistinguishable from noise is deleted, with its constants, its tests and its documentation
- [ ] #4 Suite green and the eval set no worse overall after the deletions
- [ ] #5 A stated bar for admitting future ranking factors, recorded where the next author will find it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
