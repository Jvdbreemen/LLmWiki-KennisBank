---
id: TASK-138
title: 'Measure the ceiling for reranking the top-20 memory candidates, then decide'
status: To Do
assignee: []
created_date: '2026-08-11 17:19'
labels:
  - retrieval
  - research
  - memory
dependencies: []
references:
  - docs/research/l2-scene-retrieval-2026-08.md
  - scripts/scene-experiment.py
  - scripts/_rank.py
  - scripts/kb-recall.py
priority: high
ordinal: 132700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The TASK-134 measurements put the memory-layer bottleneck in ranking, not retrieval. Of the 209 questions the baseline misses at k=5 on the 856-question dev split:

| Where the gold memory actually sits | Count |
| --- | --- |
| in the top 20 | 130 |
| in the top 50 | 158 |
| in the top 200 | 186 |
| absent or beyond 200 | 23 |

Median rank when found: 11. So retrieval surfaces the right memory for 186 of 209 misses and ranks it out of the window.

What that is worth, against the alternatives already measured:

| Configuration | recall@5 | recall@1 |
| --- | --- | --- |
| baseline | 0.756 | 0.334 |
| L2 scene tier, perfectly clustered (upper bound, TASK-134) | 0.796 | 0.338 |
| perfect reranking of the top 20 | 0.908 | 0.908 |

A reranker over 20 short candidates is also the shape of LLM task the local models handle: the scene extractor failed on a 32k-token prompt that required echoing 1508 ids, whereas ranking 20 snippets is a small, bounded prompt.

**Gate before implementation.** This task is measurement first. Do not build a reranker until the ceiling is computed and a cheap baseline reranker is compared against it. The lesson from TASK-134 is that a ceiling costs minutes and decides whether the implementation is worth days — and that the ceiling must be computed for the mechanism that will actually run (see TASK-137: the scene ceiling assumed a routing rule the code did not use).

Scope for this task: the ceiling, an arm harness reusing scripts/scene-experiment.py's cached query vectors, and one cheap reranker measured against it. The decision to ship anything is out of scope until the numbers exist.

Constraints carried over: the reranker runs on the hot path, so its latency budget is the sub-second recall path (baseline p50 is roughly 100 ms warm); it must fail open to the current ranking; and it must be measured on the dev split only, with holdout and kb-memory-eval-set-v2.json reserved for confirming a winner.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The exact ceiling is reported: recall@1 and recall@5 achievable by a perfect reranking of the top-N pool, for N in {5, 20, 50}, on the dev split
- [ ] #2 The ceiling is computed for the pool the production path actually retrieves (same floor, same layer filter), not an idealised one
- [ ] #3 At least one cheap reranker is measured against the baseline with per-question flips and an exact McNemar p-value
- [ ] #4 Latency p50 and p95 are reported per arm from a warm query-vector cache, with the run-to-run spread stated
- [ ] #5 The arm fails open to the current ranking when the reranker is unavailable, proven by a test
- [ ] #6 A written decision states whether to proceed, with the numbers that support it, including what did not work
- [ ] #7 python -m pytest tests -q is green
<!-- AC:END -->
