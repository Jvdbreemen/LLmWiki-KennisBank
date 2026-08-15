---
id: TASK-163
title: Ablate the ranking factors the reranker makes redundant
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 12:30'
labels: []
dependencies: []
ordinal: 102400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the field review (docs/research/agent-memory-field-review-and-strategy.md).
A removal task, deliberately sequenced AFTER the TASK-138 rerank decision.

`_rank.py` multiplies seven signals on the memory layer: relevance (hybrid RRF)
x recency (per-type half-life + floor) x importance (judge 1-5) x trust
(evidence_basis) x usage (1.10/1.05) x noise (up to -20%, floor 0.80) x coupling
(1.05/1.10), plus graph-neighbour expansion. Each was introduced with its own
justification and judged by whether the total moved recall@k.

That this family hides expensive mistakes is not a hypothesis. The embedding
sweep (docs/research/embedding-model-sweep-2026-08.md) found the largest member
of it actively harmful: disabling the FTS5 lexical half raises memory recall@5
from 0.641 to 0.796, and the same shift appears across six of nine models. A
fifteen-point defect survived inside the product because the product was only
ever evaluated as a whole.

WHY THIS WAITS FOR TASK-138. A cross-encoder reranking the top 20 re-scores the
candidate set directly, so factors whose job is to nudge ordering within that set
become redundant at best and contradictory at worst. Ablating seven multipliers
that a reranker will replace is wasted work; shipping a reranker on top of seven
unexamined multipliers buries the reason it under-performs. Decide the reranker,
then ablate what it makes redundant.

The harness exists: TASK-86 (frozen eval runs at hook parity), TASK-72 (observed
rank as selection criterion), scripts/recall-ablation.py (already used for the
dense-versus-lexical split). Pin a usage snapshot and stay within one index state
on one day — the L2 scene report documents how a date boundary alone reordered
146 of 856 questions.

Standing consequence: no new ranking factor joins the product without measured
contribution, including the outcome signal from TASK-166.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Runs after the TASK-138 rerank decision, and states which factors that decision makes redundant before measuring
- [ ] #2 Per-factor ablation against the frozen memory eval set, within one index state on one day, usage snapshot pinned
- [ ] #3 Method and full result table written down, including factors that stayed
- [ ] #4 Every factor whose delta is indistinguishable from noise is deleted with its constants, tests and documentation
- [ ] #5 The lexical-fusion finding is resolved rather than carried forward a third time
- [ ] #6 Suite green, eval no worse overall, and a stated bar for admitting future ranking factors
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
