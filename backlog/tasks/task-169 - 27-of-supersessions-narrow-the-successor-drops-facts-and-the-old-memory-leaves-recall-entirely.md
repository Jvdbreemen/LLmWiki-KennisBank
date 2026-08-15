---
id: TASK-169
title: >-
  27% of supersessions narrow: the successor drops facts and the old memory
  leaves recall entirely
status: Done
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


## Where the acceptance criteria stand

Evidence: `docs/research/narrowed-supersede-2026-08-16.md`.

- #1 met as keep-both, not merge. Both closing judges (RECONCILE_SYSTEM v3,
  SUPERSEDE_SYSTEM v3) require full coverage; partial coverage routes to
  ADD / supersede:false. Replayed on all 209 adjudicated pairs: knowledge-losing
  closures on NARROWED drop 57.8% -> 37.5%; the duplicate defence never rested
  on this judge (write-time dedup + exact_duplicate_pass) and is unchanged.
  Merge-forward was deliberately rejected: it would use the operation class
  being repaired as the repair.
- #2 met: 64/64 reopened via _memory.reopen(), 0 failed, exactly 64 files
  re-indexed. Gate: oldest-wins dev 0.000 -> 0.333 r@5 (production) / 0.600
  (cosine). Bonus finding for TASK-162: with old answers finally in the pool,
  recency buries them (0.333 vs 0.600).
- #3 met: healing touched only NARROWED stems; 145 DUPLICATE closures untouched,
  and v3 does not weaken the non-LLM duplicate paths.
- #4 met: 1436 passed, 2 skipped. Memory-layer regression eval (n=1224):
  +0.000/+0.002/+0.001 — reopening added answers without disturbing existing
  ones.

Residual risk, stated: v3 still closes 37.5% of NARROWED pairs on replay. The
healed 64 are events (pre-volatility) and the maintenance pass never closes
events; the exposure is write-time reconcile against future candidates, and
every such closure carries `promptversie 3` in the closed-log, so the rate is
auditable rather than silent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A supersede decision can produce a merge-or-keep outcome when coverage is partial, measured against the 64 adjudicated NARROWED pairs
- [x] #2 The 64 historic NARROWED closures are healed (reopened or merged forward), with the freshness oldest-wins questions as the gate
- [x] #3 No regression on DUPLICATE handling: the 145 adjudicated duplicates must stay closed
- [x] #4 python -m pytest tests -q is green
<!-- AC:END -->
