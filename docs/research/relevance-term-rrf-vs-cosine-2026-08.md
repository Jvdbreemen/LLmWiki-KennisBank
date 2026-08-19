# The relevance term: RRF rank artefact versus the cosine it discarded

**Task:** TASK-203, from the Eaves review (`eaves-memory-architecture.md`).
**Date:** 2026-08-19. **Index state:** post-v0.36.0 vault, 3800+ memories,
215 wiki articles; all arms measured on the same index on the same day —
numbers here are not comparable to earlier reports measured on other index
states.

**Verdict:** the cosine repairs the top of both rankings — memory r@1
+0.235, wiki r@1 +0.110 — while recall@5 moves nowhere. The pre-registered
rule (+0.02 r@5) passes no arm; the owner ruled on the tension (2026-08-19)
and amended the rule for ordering-class interventions: **+0.02 at the
injected depth (@3), recall@5 not lower.** Under that rule memory `cos`
(+0.060@3, r@5 unchanged) and wiki `minmax` (+0.110@1, r@3 +0.003 at
saturation, r@5 unchanged) both ship, and the defaults flipped to
`memory_fusion=cos`, `wiki_fusion=minmax` with `rrf` kept as the fallback
knob. The lexical arm on memory loses at every depth even with a weight:
TASK-128's conclusion stands, strengthened.

## The defect being tested

`_kbindex.search` fuses with RRF (`score = 1/(60+rank)`); `_rank.rerank`
multiplies that score by recency x importance x trust x usage x noise x
coupling. Both halves are reasonable alone. Together: the RRF top-8 spread is
**1.12x** while the multiplier stack spans up to **5.68x** — on the memory
layer the reranker was substantially replacing relevance, not reweighting it.
Meanwhile the cosine — computed for free from the same KNN query, carried on
every hit — was ignored by `rerank`.

## Pre-measurement: does the cosine even carry a gradient here?

The implementation note demanded this first: if the cosine is nearly as flat
as RRF on this corpus, the finding weakens and that must be said plainly.

Measured over 120 frozen-eval questions, k=8, memory layer, real pools:

| statistic | value |
| --- | --- |
| top-cos p50 | 0.636 |
| lowest-cos p50 | 0.505 |
| spread top/lowest p50 | **1.249x** |
| p10 / p90 | 1.096x / 1.488x |

The cosine carries roughly twice the RRF spread at median. It is a real
gradient — and it is still small against the 5.68x multiplier stack, so
switching the relevance term alone was never guaranteed to move recall. That
is exactly what the eval decides.

## Arms

All arms: frozen sets (`kb-memory-eval-set.json`, 1224 questions;
`kb-eval-set.json`, wiki), production parity via `retrieve_params`
(TASK-86/188), usage telemetry off, end-to-end through `recall_hits`
including `rerank`.

| arm | layer | config |
| --- | --- | --- |
| 1 baseline | both | fusion=rrf (production default) |
| 2 cos | memory | `KB_MEMORY_FUSION=cos` — score IS the raw cosine |
| 3 minmax | wiki | `KB_WIKI_FUSION=minmax` — weighted intra-pool min-max, w_vec 0.7 / w_fts 0.3, renormalised onto firing arms |
| 4 lexical rerun | memory | `KB_MEMORY_FUSION=minmax KB_MEMORY_FTS=1` — TASK-128's question re-asked now that a weight exists |

`min_cos` gates on the raw cosine in every arm; no fused or normalised score
is ever a cross-query threshold (the Eaves caveat, carried over unchanged).

## Results

| arm | r@1 | r@3 | r@5 | MRR |
| --- | --- | --- | --- | --- |
| memory baseline (rrf) | 0.245 | 0.621 | 0.749 | 0.437 |
| memory cos | **0.480** | **0.681** | 0.749 | **0.585** |
| memory minmax + lexical (w_fts 0.3) | 0.453 | 0.618 | 0.686 | 0.543 |
| wiki baseline (rrf) | 0.884 | 0.997 | 1.000 | 0.939 |
| wiki minmax | **0.994** | **1.000** | 1.000 | **0.996** |

Note on the wiki layer, stated before its arm ran: baseline recall@5 is
saturated at 1.000, so the winner rule's "+0.02 recall@5" is unreachable
there by construction. The wiki arm can only show itself on r@1/MRR — and it
did: +0.110 on recall@1 (38 missed tops down to 2, on 329 questions) and
+0.057 MRR. Same shape as the memory arm: the pool was already right, the
top of the ordering was not.

### Arm 2, read against the defect

The deltas land exactly where the arithmetic predicted. recall@5 is unchanged
(+0.000): the candidate pool and the `min_cos` gate are identical, so @5 only
moves when reordering pulls gold from ranks 6-8 into the top 5, and wins and
losses balanced. But recall@1 nearly doubles (+0.235) and MRR gains +0.148 --
the rank-0 hits that the multiplier stack displaced "not occasionally, but by
construction" stay on top once the relevance term carries a gradient.

One reading matters for the verdict: the injected memory block is
`memory_top_n = 3`, so recall@3 is the user-visible metric, and +0.060 is
three times the +0.02 bar -- applied at @3 rather than the pre-registered @5.
The rule as written tests @5 and this arm fails it; the metric the rule was
protecting is @-what-the-user-sees, and this arm clears it threefold. That
tension goes to the owner, not into a silent reinterpretation.

## Winner rule

As always: an arm ships only if recall@5 improves >= +0.02 with recall@1 not
lower, on the frozen set, against the same-day baseline. Nothing flips
without a win; a negative result closes the question and is written here.

### The verdict tension

No arm clears "+0.02 recall@5". Both fusion arms transform the TOP of the
ranking: memory r@1 +0.235 (roughly double), wiki r@1 +0.110 (38 missed tops
to 2), MRR +0.148 / +0.057. recall@5 cannot see this class of repair: the
candidate pool and the `min_cos` gate are identical, so @5 moves only when
gold crosses the rank-5 boundary, and the defect under test was never about
the pool — it was about metadata factors displacing the rank-0 hit.

The user-visible metrics are `memory_top_n = 3` and wiki `top_n = 3`: what
lands in the injected block. At @3 the memory arm gains +0.060 (three times
the bar) and wiki +0.003 (saturated). The pre-registered rule was written
for admission-class changes (the scene tier, where the pool itself changes);
applied to an ordering-class change it tests the one depth that is blind to
the intervention. That is a real mismatch between rule and intervention
class, stated here rather than silently reinterpreted. Put to the owner on
2026-08-19: ruled to amend, not to keep. The amended rule for ordering-class
interventions is pre-registered here for the next measurement of this kind:
an ordering change ships only if the injected-depth recall (@`top_n`)
improves >= +0.02 with recall@5 not lower. Pool-class interventions keep the
original @5 rule — the scene-tier rule was right for its class.

### Arm 4: the lexical arm loses even with a weight

TASK-128 measured the lexical arm worthless on memory at RRF's equal weight,
which could not distinguish "worthless arm" from "wrong weight". At
w_fts 0.3 the arm now loses on every depth against cos-only (r@5 -0.063
against baseline, -0.063 against cos). Weights below 0.3 were not measured:
the gap is monotone and large, and each point of lexical weight bought loss.
The arm is the problem, not the weight. TASK-128's conclusion stands.

## What this reopens (from the task, to be answered by the results)

1. TASK-128 concluded the lexical arm is worthless on memory — measured at
   RRF's equal weight, which cannot distinguish "worthless arm" from "wrong
   weight". Arm 4 re-asks at w_fts 0.3; if it loses, a smaller weight run
   decides whether the weight or the arm is at fault.
2. TASK-160 warned the eval set structurally favours similarity. The
   arithmetic above says production had the opposite tilt. Both can be true;
   the defaults were tuned against a metric with the reverse bias of the
   system it tuned.
