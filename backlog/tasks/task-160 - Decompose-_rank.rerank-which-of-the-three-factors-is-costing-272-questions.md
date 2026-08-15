---
id: TASK-160
title: 'Decompose _rank.rerank: which of the three factors is costing 272 questions?'
status: Done
assignee: []
created_date: '2026-08-14 04:11'
updated_date: '2026-08-14 06:02'
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
- [x] #1 Each factor is measured alone and removed, on the same cached pool and split as TASK-138
- [x] #2 Every arm is compared to production with an exact McNemar p-value and per-question flips in both directions
- [x] #3 The factor carrying most of the loss is named, with the numbers behind the claim
- [x] #4 Any interaction between factors is reported rather than assumed absent
- [x] #5 The report states that the eval set favours similarity, and what that means for acting on the result
- [x] #6 python -m pytest tests -q is green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Recency, mostly. Report: docs/research/rank-factors-2026-08-14.md.

    arm              recall@1   gained@1  lost@1   p
    production        0.2640        -        -     -
    no recency        0.4112       146      20    <1e-6
    no importance     0.3178        71      25    3e-6
    no trust          0.2640         0       0    1.0
    no usage          0.2605        10      13    0.68
    no noise          0.2640         0       0    1.0
    all neutral       0.5572       272      21    <1e-6

**The control passed**, which is what makes the rest usable: neutralising every factor reproduces the raw-cosine ordering on all 856 questions, zero differences. Nothing outside these factors reorders, so the decomposition is complete rather than merely plausible.

**Recency carries 50% of the loss** (+0.147 of +0.293), importance 18%. Usage is indistinguishable from noise (p = 0.68).

**Why a 40% factor can overwrite a ranking.** RRF scores rank r at 1/(60+r), so adjacent ranks differ by 1.6%. Recency spans 0.6-1.0, importance 0.9-1.1. Every factor is larger than the gap between the ranks it multiplies into: these are not tie-breakers, they are large enough to replace the ranking. A document at rank 8 with recency 1.0 beats one at rank 1 with 0.6.

**Two factors do literally nothing, and the reason is structural.** `no trust` and `no noise` give byte-identical results — zero flips. All 1732 current memories carry `evidence_basis: agent`, so `trust_factor` returns 0.95 for every one of them, and a uniform multiplier cannot reorder. It is inert until the vault holds human-typed or imported memories, at which point it starts working with no warning. Recorded so a future measurement does not rediscover the same non-effect and conclude the factor is harmless.

**The factors compound** (AC#4): individual removals sum to +0.203 while joint removal gives +0.293. A third of the loss exists only in combination, so tuning them one at a time under-measures.

**AC#5, and it is the reason nothing is being changed:** the eval set is generated one question per document, so it structurally penalises recency — the very thing recency exists to do. This metric would report recency as harmful even if it were working perfectly. A freshness-aware question set is the prerequisite for acting here.

The one tuning question worth asking when that set exists: `RECENCY_FLOOR = 0.6` permits a 40% swing against 1.6% rank gaps. Raising the floor would keep the preference for fresh knowledge without letting it overwrite the ranking.
<!-- SECTION:FINAL_SUMMARY:END -->
