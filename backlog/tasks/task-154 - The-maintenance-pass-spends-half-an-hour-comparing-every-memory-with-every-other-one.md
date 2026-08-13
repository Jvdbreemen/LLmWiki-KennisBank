---
id: TASK-154
title: >-
  The maintenance pass spends half an hour comparing every memory with every
  other one
status: Done
assignee: []
created_date: '2026-08-13 17:52'
updated_date: '2026-08-13 19:43'
labels:
  - performance
  - memory
  - index
dependencies: []
priority: high
ordinal: 148700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured on the live vault (1595 current memories), 2026-08-13, with the new progress helper from TASK-153 — which is how it became visible at all:

- `similar_pairs()` walks 1,271,315 pairs. Pure-Python cosine, roughly 15 minutes.
- `cluster_promote_pass()` calls `neighbor_counts()`, which walks the same triangle again.

So every background sweep spends around half an hour of CPU to find, on this corpus, ten pairs above 0.85. That is the opposite of "heavy work off the hot path": it is heavy work that runs every time and finds almost nothing. It also grows quadratically — at 3000 memories it is four times as long.

The index already holds exactly these vectors in a structure built for this question. `kb-index.db` carries the memory layer under a known `embed_id` (this is what made `current_items()` drop from 600s to 16.8s in TASK-148). Instead of comparing everything with everything, ask the index per memory for its nearest neighbours above the threshold — a bounded query per item rather than an unbounded triangle.

Keep the current implementation as the fallback for when the index is absent, stale or in a different embed space. Correctness there is not negotiable: comparing across embedding spaces is silently meaningless.

Measure before and after on the same corpus, and prove the pair set is identical — or state exactly which pairs the KNN bound drops and why that is acceptable. A faster pass that finds different pairs is a behaviour change, not an optimisation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 similar_pairs and neighbor_counts use the index for candidate lookup when it is valid for the active embed_id
- [x] #2 The brute-force path stays as the fallback when the index is missing, stale or in another embed space
- [x] #3 The pair set from the fast path is proven identical to the brute-force result on the live corpus, or every difference is listed and justified
- [x] #4 Before and after timings are recorded on the same corpus
- [x] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Measured on the live vault, 2026-08-13, 1595 current memories

    brute force   163 pairs in 1171.86s
    index path    163 pairs in  106.94s     11x
    pair sets IDENTICAL; largest cosine difference 4.01e-07

The cosine difference is float32 storage in the index against float64 in
Python, seven orders of magnitude below any threshold in this codebase.

## Why the shortcut is exact and not an approximation

vec0 returns rows ordered by distance, and for unit vectors distance and cosine
are monotonically related. So if the k-th row already sits below the threshold,
no row past k can sit above it — the answer is provably complete. Only when the
whole window is still above the threshold can anything be missing, and then the
window widens (32 → 128 → …). A fixed k would be a silent truncation, which is
the exact class of bug this codebase has spent the week removing.

Three ways the index can be wrong, all of which decline rather than guess: no
index, a different `embed_id` (cosine across two embedding spaces is
meaningless), and an index not marked unit-normalised (the distance-to-cosine
conversion does not hold). Each returns None and the brute-force path runs.

## The gap found by re-reading the first version

A memory the index has not seen cannot come out of it — and that is not a rare
edge case but the NORMAL state after every sweep, because the sweep writes
memories and the index catches up afterwards. Two freshly captured memories
would therefore never have found each other, and `supersede_pass` would have
reported a clean zero. Silent incompleteness, in the newest memories, which are
the ones reconcile cares about most.

So the fast path is a hybrid: the index answers for what it knows, and anything
it does not know is compared against everything the old way. That costs
O(unindexed × all), which is nothing while the backlog is small, and the answer
is exact regardless of how far behind the index has fallen. Pairs are deduped
because the loose arm writes both directions.

## What the 11x is and is not

The remaining 107s is not distance arithmetic — 2.9e9 multiply-adds in C would
take seconds. It is per-query overhead: 1595 round-trips through SQLite, each
serialising a 1024-float query vector. Going further would need a different
shape entirely (one pass computing the whole similarity matrix), and at this
corpus size that is not worth the complexity. `cluster_promote_pass` walks the
same triangle with `neighbor_counts`, so the sweep as a whole goes from roughly
half an hour to roughly three and a half minutes.
<!-- SECTION:NOTES:END -->
