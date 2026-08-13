---
id: TASK-154
title: >-
  The maintenance pass spends half an hour comparing every memory with every
  other one
status: To Do
assignee: []
created_date: '2026-08-13 17:52'
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
- [ ] #1 similar_pairs and neighbor_counts use the index for candidate lookup when it is valid for the active embed_id
- [ ] #2 The brute-force path stays as the fallback when the index is missing, stale or in another embed space
- [ ] #3 The pair set from the fast path is proven identical to the brute-force result on the live corpus, or every difference is listed and justified
- [ ] #4 Before and after timings are recorded on the same corpus
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->
