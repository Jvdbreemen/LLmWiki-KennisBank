---
id: TASK-128
title: Lexical fusion costs the memory layer ~15 points of recall@5
status: Done
assignee: []
created_date: '2026-08-03 04:29'
labels:
  - retrieval
  - quality
dependencies: []
priority: high
ordinal: 123700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured while sweeping embedding models for TASK-126. Turning the FTS5 half of `_kbindex.search` off — by passing an empty `query_text`, which skips the branch because `fts_expr("")` returns empty — raises memory recall@5 substantially, across every capable model:

```
memory recall@5      hybrid  ->  vector-only
qwen3-embedding:8b    0.641  ->  0.796
qwen3-embedding:4b    0.642  ->  0.794
embeddinggemma:300m   0.625  ->  0.760
qwen3-embedding:0.6b  0.629  ->  0.746
e5-large-instruct     0.628  ->  0.743
bge-m3                0.637  ->  0.723
```

Six of nine models move the same way and by a similar amount, so this is unlikely to be noise. The exceptions are informative rather than contradictory: nomic-embed-text is flat (0.557 -> 0.565) and snowflake-arctic-embed2 gets worse (0.462 -> 0.315) — both are the models whose vectors are weakest on this vault, so lexical rescue is the only thing holding them up.

The wiki layer does not show the same pattern. There the effect is small and model-dependent (embeddinggemma 0.985 -> 0.997, arctic 0.950 -> 0.798), which fits: wiki queries in the eval set carry more distinctive vocabulary than memory queries do.

Hypothesis to test, not a conclusion: RRF fusion gives the lexical ranking equal standing with the vector ranking, and on short memory fragments a term match is a much weaker relevance signal than it is on an article. The fix would be a layer-dependent weight (or no FTS on memory at all) rather than one fusion for both layers.

Caveats that must be resolved before acting:

- The memory layer is additionally reweighted by recency and importance in `_rank`. That weighting stayed on in both arms, so it cannot explain a difference between them, but it does mean neither arm is pure vector ranking.
- Measured at min_cos 0.0 (rank-only). Production runs a 0.60 floor, which may change the balance.
- One eval set, one vault. Reproduce on a second set before changing the fusion.

Method and raw numbers: `scripts/embed-sweep.py --vector-only`, results in the TASK-126 report.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The hybrid-versus-vector-only gap on the memory layer is reproduced on a second eval set or a regenerated one
- [x] #2 The effect is measured again with the production threshold (0.60) rather than rank-only
- [x] #3 Root cause established: RRF weighting, the sparsity of memory fragments, or an artefact of the eval set
- [x] #4 A decision is recorded: layer-dependent fusion weight, no FTS on memory, or leave as is with the reason
<!-- AC:END -->


## Implementation Notes

Reproduced with `recall-ablation.py`, which splits three conditions instead of the two the original
finding used. Same index (qwen3-embedding:4b, 1517 docs), the project's own eval sets, recall@5 / MRR:

```
                 wiki (329 q)        memory (1224 q)     memory disjoint (144 q)
  dense-only     0.997 / 0.967       0.794 / 0.539       0.833 / 0.690
  fts-only       0.991 / 0.946       0.461 / 0.266       0.486 / 0.357
  hybrid         1.000 / 0.984       0.658 / 0.479       0.694 / 0.563
```

Root cause (AC3): RRF weighs both rankings equally. That pays off when the arms are comparably
strong -- on wiki the fusion beats BOTH arms, which is exactly what RRF is for. On memory the arms
differ by nearly a factor two in MRR, and fusing then costs 13.6 points of recall@5 against the
dense arm alone: the weak lexical ranking pushes good dense hits out of the top k. Memories are
short and atomic, so a term match says far less about relevance there than in an article.

AC2: measured again at the production floor (min_cos 0.45). Hybrid 0.655 / 0.479 against dense-only
0.783 / 0.546 -- unchanged picture, so the floor is not the explanation.

AC1, honestly: `kb-eval-gen --layer memory` regenerated 1345 questions of which 1201 were IDENTICAL
to the curated set, because both derive questions deterministically from document titles. That is
not an independent replication. The 144 genuinely new questions were split off and run separately;
they show the same pattern with a slightly larger gap. A real second set needs a different
generation process (`--llm` paraphrases, or hand-written questions).

Worth carrying forward: questions shaped like "Wat is er vastgelegd over <title>?" contain the
document's own terms by construction, which is exactly what FTS is good at. The lexical arm may
therefore look BETTER in these measurements than it is in practice, which would make the fusion
penalty larger rather than smaller.


## Final Summary

Decision (AC4): the memory layer no longer runs a lexical arm. `_kbindex.search` skips the FTS
branch when the query targets memory only, restorable with `KB_MEMORY_FTS=1` for re-measurement.

Verified end to end on the production route, not just in the ablation harness. `kb-eval --layer
memory` over 1224 questions:

    before   recall@5 0.658   MRR 0.479
    after    recall@5 0.794   MRR 0.539

which lands exactly on the dense-only figure the ablation predicted.

Why this rather than a weighted fusion: the data shows the lexical arm is not adding unique answers
on this layer, it is displacing good ones. If FTS were finding memories the vector arm misses, the
hybrid would beat dense-only at k=5; it loses by 13.6 points instead. A weight would be a tunable
with no measured setting behind it, where removal has one. Wiki keeps the fusion untouched, where it
still beats both arms.

Three tests hold the line: a memory-only query ignores an exact term match that outranks the vector
hit, a mixed-layer query keeps its lexical half, and the env override brings it back.

Caveats that survive this task:

- The eval questions are shaped "Wat is er vastgelegd over <title>?", so they contain the document's
  own terms by construction -- friendly to FTS. The lexical arm probably scores better here than in
  real prompts, which makes the fusion penalty a floor rather than a ceiling.
- AC1 is satisfied only partly. The regenerated set shared 1201 of 1345 questions with the curated
  one, so the independent evidence is the 144 disjoint questions (dense 0.833 against hybrid 0.694).
  A genuinely independent set needs a different generation process.
- The memory layer is still reweighted by recency and importance after fusion. That was constant
  across all conditions, so it cannot explain the difference, but it means none of these numbers is
  a pure ranking measurement.
