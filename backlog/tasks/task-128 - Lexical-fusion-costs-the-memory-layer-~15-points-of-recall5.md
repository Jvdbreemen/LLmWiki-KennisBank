---
id: TASK-128
title: Lexical fusion costs the memory layer ~15 points of recall@5
status: To Do
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
- [ ] #1 The hybrid-versus-vector-only gap on the memory layer is reproduced on a second eval set or a regenerated one
- [ ] #2 The effect is measured again with the production threshold (0.60) rather than rank-only
- [ ] #3 Root cause established: RRF weighting, the sparsity of memory fragments, or an artefact of the eval set
- [ ] #4 A decision is recorded: layer-dependent fusion weight, no FTS on memory, or leave as is with the reason
<!-- AC:END -->
