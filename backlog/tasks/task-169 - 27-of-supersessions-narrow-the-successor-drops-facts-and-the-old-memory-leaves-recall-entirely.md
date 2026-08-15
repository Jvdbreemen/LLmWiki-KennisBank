---
id: TASK-169
title: >-
  27% of supersessions narrow: the successor drops facts and the old memory
  leaves recall entirely
status: To Do
assignee: []
created_date: '2026-08-15 22:05'
labels:
  - memory
  - supersede
  - data-loss
  - measurement
dependencies: []
priority: high
ordinal: 162700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by TASK-161's labelling, adjudicated pair by pair with adversarial verification (docs/research/freshness-eval-2026-08-16.md).

Of 237 `superseded_by` pairs in the vault, 64 (27%) are NARROWED: the successor covers less than the memory it closed. A fallback path, a concrete parameter (`RRF k=60`), a disable procedure — facts whose only carrier was the old memory. Closing it removes that carrier from recall, because `recall_hits` filters on `status=current`. Not ranked lower; unreachable.

Measured consequence: 30 eval questions whose correct answer is a narrowed-away old memory score 0.000 recall in BOTH ranking arms, with non-empty pools. The ranking never gets the chance to be wrong — the filter already lost the knowledge.

Only 11% of supersessions actually REPLACED substance. The machinery treats "newer statement about the same subject" as "complete replacement", and that assumption is wrong in the knowledge-losing direction more than twice as often as it is right.

Directions worth weighing, not decided here:

1. **Reconcile asks the wrong question at write time.** It asks whether the new memory covers the old before closing it; a "partly" should lead to MERGE (carry the dropped facts into the successor) or ADD (keep both), never SUPERSEDE. The prompt and action set exist (`_reconcile.py`); this is a third outcome, not a new pass.
2. **The supersede maintenance pass has the same blind spot** at a different threshold (`SUPERSEDE_THRESHOLD = 0.75` on cosine): high similarity does not mean full coverage — 61% of historic closures were duplicates but 27% narrowed.
3. **Backfill is possible and bounded**: the 64 NARROWED pairs are already identified by stem in the freshness set. Reopening the old memory (or merging its dropped facts forward) is 64 file edits, each already adjudicated.

Ready-made regression gate: the oldest-wins half of `06-claude/kb-freshness-eval.{dev,holdout}.json` scores zero today by construction. The day a NARROWED-aware supersede lands, those questions must stop scoring zero — no new instrument needed.

<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A supersede decision can produce a merge-or-keep outcome when coverage is partial, measured against the 64 adjudicated NARROWED pairs
- [ ] #2 The 64 historic NARROWED closures are healed (reopened or merged forward), with the freshness oldest-wins questions as the gate
- [ ] #3 No regression on DUPLICATE handling: the 145 adjudicated duplicates must stay closed
- [ ] #4 python -m pytest tests -q is green
<!-- AC:END -->
