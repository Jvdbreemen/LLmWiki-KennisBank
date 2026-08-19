---
id: TASK-203
title: >-
  The reranker multiplies metadata onto a relevance term RRF flattened to 1.1x
status: In Progress
assignee: []
created_date: '2026-08-16 12:00'
updated_date: '2026-08-16 16:30'
labels: []
dependencies: []
ordinal: 167800
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Eaves review (docs/research/eaves-memory-architecture.md). Their
`fuseScores` comment says RRF "keeps only rank and, on a small corpus,
collapses every hit into a ~0.03 blur", while weighted min-max "preserves the
gradient". Checking whether that criticism lands here turned up something
larger than a fusion choice.

`_kbindex.search` fuses with RRF: `score = 1/(60 + rank)`. `_rank.rerank` then
multiplies that score by recency x importance x trust x usage x noise x
coupling. Both halves are reasonable on their own. Together the arithmetic does
not work out.

RRF spread of the relevance term (exact, k=60, single arm — the memory layer's
configuration since TASK-128 removed its lexical arm):

| candidates | top score | last score | spread |
|---|---|---|---|
| top-5 | 0.01667 | 0.01562 | **1.07x** |
| top-8 | 0.01667 | 0.01493 | **1.12x** |
| top-20 | 0.01667 | 0.01266 | **1.32x** |

Spread of the multipliers stacked on top of it:

| factor | range | spread |
|---|---|---|
| recency (floor 0.6) | 0.600 .. 1.000 | 1.67x |
| noise | 0.800 .. 1.000 | 1.25x |
| importance | 0.900 .. 1.100 | 1.22x |
| trust | 0.950 .. 1.050 | 1.11x |
| usage | 1.000 .. 1.100 | 1.10x |
| coupling | 1.000 .. 1.100 | 1.10x |
| **all combined** | 0.246 .. 1.398 | **5.68x** |

On a top-8 memory recall, **recency alone (1.67x) outweighs the entire
relevance ordering (1.12x)**, and the six factors together outweigh it by
roughly five to one. A rank-7 hit that is fresh, important and recently used
displaces the rank-0 hit — not occasionally, but by construction. The reranker
is not reweighting relevance; on the memory layer it is substantially replacing
it.

Worth being precise about what is and is not broken. With one arm, RRF is a
monotone transform of the vector ranking, so the order going *in* to `rerank`
is correct. The defect is purely that the magnitude is compressed to almost
nothing while the multipliers are not, so any metadata factor dominates. In the
two-layer path FTS does run and a doc present in both rankings gets up to 2x —
the only large relevance signal RRF emits — which is still small against 5.68x.

**The cosine is already there.** `_kbindex.search` computes `cos` via
`_cosine_from_l2` — whose own comment says it is free, because the distance
comes out of the same KNN query and was being thrown away until now (original
Dutch: "Dat is gratis: de afstand komt uit dezelfde KNN-query en werd tot nu
toe weggegooid") — returns it on every hit, and
`kb-recall.recall_hits` carries it through into the dicts `rerank` receives.
`rerank` reads `h.get("score")` and ignores `h.get("cos")`. The signal with the
real gradient is computed, carried, and then not used.

So the fix is not to import Eaves' fusion — it is to stop discarding what we
already have:

- **Memory layer (single arm).** Use `cos` as the relevance term instead of the
  RRF rank artefact. No fusion involved, nothing new computed.
- **Wiki layer (two arms).** Here a fused score is genuinely needed, and this is
  where Eaves' mechanism earns its place: min-max normalise each signal within
  the pool, weight them, and renormalise the weights onto whichever arms
  actually fired so a single-arm query is not scaled down.

Carry one caveat over from their code unchanged: min-max is intra-query
relative, never cross-query calibrated — the best item in any pool lands near
1.0 even for an off-topic query. Neither the fused score nor a normalised
cosine may become a `score > X` gate. `min_cos` keeps gating on the raw cosine
where it does today.

Two things this reopens:

1. **TASK-128's conclusion.** The lexical arm was measured worthless on memory
   at RRF's equal weight. That measurement cannot distinguish "the arm is
   worthless" from "equal weight is wrong", because RRF has no weights.
2. **TASK-160's warning**, from the other side. It observed that the eval set
   "structurally favours similarity and penalises recency and importance". The
   arithmetic above says production has the opposite bias: relevance is
   flattened and the metadata factors decide. Both can be true at once, and
   together they mean the factor defaults were tuned against a metric with the
   reverse tilt of the system it was tuning.

Winner rule as usual: nothing flips without beating the current default on the
frozen eval set. A negative result is a real finding and closes the question.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The relevance term entering `rerank` on the memory layer is the cosine, not the RRF rank artefact, behind a flag until measured
- [x] #2 Relevance and the metadata multipliers are on comparable scales; the measured spread of each is written down, not assumed
- [x] #3 Weighted min-max fusion is implemented for the two-arm (wiki) path and renormalises onto the arms that actually returned candidates
- [x] #4 `min_cos` still gates on the raw cosine; no normalised or fused score is ever used as a cross-query threshold
- [x] #5 The frozen eval set reports baseline versus cosine-relevance versus weighted fusion, on memory and on wiki separately
- [x] #6 TASK-128's lexical-arm question is re-run at a small weight, now that a weight exists
- [x] #7 Defaults change only on a win under the winner rule; numbers and method are written up in docs/research/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reproduce the spread table with `_rank.py`'s own factor functions and
`1/(60+rank)`; it is arithmetic, not a measurement, and needs no vault. The
cosine spread across a real candidate pool DOES need the vault and is the first
thing to measure — if the cosine turns out to be nearly as flat as the RRF
score on this corpus, the finding weakens considerably and that should be said
plainly rather than worked around.
<!-- SECTION:NOTES:END -->
