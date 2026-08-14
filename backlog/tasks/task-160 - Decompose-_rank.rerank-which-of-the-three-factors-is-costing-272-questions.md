---
id: TASK-160
title: 'Decompose _rank.rerank: which of the three factors is costing 272 questions?'
status: To Do
assignee: []
created_date: '2026-08-14 04:11'
updated_date: '2026-08-14 04:11'
labels:
  - retrieval
  - research
  - memory
dependencies: []
priority: high
ordinal: 153700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured on the 856-question dev split (TASK-138, `docs/research/rerank-ceiling-2026-08-14.md`): re-sorting the production candidate pool by raw cosine, discarding `_rank.rerank` entirely, takes recall@1 from 0.264 to 0.557 and recall@5 from 0.724 to 0.773. McNemar on hit@1: 272 gained, 21 lost, p < 1e-6.

The loss is attributable to `_rank.rerank` and to nothing else. The memory layer has no lexical arm, so RRF fuses a single ranking and is order-preserving — the RRF order *is* the cosine order. Everything between production and cosine is the multiplication by recency × importance × usage (× noise × coupling).

What is not yet known is which factor. `recency_factor` has a per-memory_type half-life, `importance_factor` scales on the judge's 1-5, `usage_factor` boosts recently used memories, and `sources_fn` adds bibliographic coupling. Any of them could be carrying the loss, or they could be interacting.

This is cheap now. The query vectors are cached from TASK-138, so each arm is a re-scoring pass over already-retrieved pools — no embedding, no model call. Arms: cosine only (measured), each factor alone, each factor removed, and production. Same pool, same split, same day, McNemar against the production arm.

**Do not flip a default on the outcome alone.** The eval set is generated one question per document, so questions are paraphrases of their gold memory. That structurally favours similarity and penalises recency and importance, which exist to serve a goal this metric cannot see: when a user asks something, the freshest memory is often the right answer even when an older one matches the words better. The decomposition tells you WHERE the loss is; a set that can measure freshness is what would let you act on it.</description>
<parameter name="acceptanceCriteria">["Each factor is measured alone and removed, on the same cached pool and split as TASK-138", "Every arm is compared to production with an exact McNemar p-value and per-question flips in both directions", "The factor carrying most of the loss is named, with the numbers behind the claim", "Any interaction between factors is reported rather than assumed absent", "The report states that the eval set favours similarity, and what that means for acting on the result", "python -m pytest tests -q is green"]
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each factor is measured alone and removed, on the same cached pool and split as TASK-138
- [ ] #2 Every arm is compared to production with an exact McNemar p-value and per-question flips in both directions
- [ ] #3 The factor carrying most of the loss is named, with the numbers behind the claim
- [ ] #4 Any interaction between factors is reported rather than assumed absent
- [ ] #5 The report states that the eval set favours similarity, and what that means for acting on the result
- [ ] #6 python -m pytest tests -q is green
<!-- AC:END -->
