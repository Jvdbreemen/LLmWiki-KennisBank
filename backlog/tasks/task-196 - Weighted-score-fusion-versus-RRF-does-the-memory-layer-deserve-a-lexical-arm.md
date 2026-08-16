---
id: TASK-196
title: >-
  Weighted score fusion versus RRF: does the memory layer deserve a lexical arm
status: To Do
assignee: []
created_date: '2026-08-16 12:00'
updated_date: '2026-08-16 12:00'
labels: []
dependencies: []
ordinal: 102400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Eaves review (docs/research/eaves-memory-architecture.md).

`_kbindex.py` fuses its vector and FTS arms with Reciprocal Rank Fusion and,
on the memory layer, has had to drop the lexical arm entirely. The comment in
`search()` is precise about the reason: "RRF weighs both rankings equally,
which pays off only when they are comparably strong: a weak ranking pushes
good hits out of the top k." On wiki the arms are close and the fusion beats
both, so it stays. On memory they differ by nearly a factor two in MRR and the
fusion beat neither (TASK-128, docs/research/embedding-model-sweep-2026-08.md).
`KB_MEMORY_FTS=1` still restores the old behaviour for re-measurement.

That measurement tested RRF-with-a-lexical-arm against vector-only. It could
not test a lexical arm at a *small weight*, because RRF has no weights — it
keeps rank and discards magnitude by construction.

Eaves' `fuseScores` (src/main/services/CoreMemoryBackend.ts) is the mechanism
that makes the untested arm testable:

- min-max normalise each signal within the candidate pool, after flipping the
  lower-is-better signals (bm25, vector distance) to higher-is-better;
- combine with a weight (theirs: `SEMANTIC_WEIGHT = 0.65`);
- renormalise the weights onto whichever signals actually fired, so a
  single-arm query still tops out near 1.0 rather than being scaled down by
  its weight.

Their stated motivation matches ours from the other side: RRF "keeps only rank
and, on a small corpus, collapses every hit into a ~0.03 blur", while weighted
min-max "preserves the gradient".

The question to settle: **is the memory layer's lexical arm worthless, or was
it only worthless at equal weight?** A literal term match is an independent
relevance signal — our own code already says so, letting FTS hits bypass the
`min_cos` floor — and removing the arm discarded that signal along with the
fusion that mishandled it.

Carry one caveat over unchanged, from their code comment: min-max is
intra-query relative, never cross-query calibrated. The best item in any pool
lands near 1.0 even for an off-topic query. The fused score may order results
and express confidence within one result set; it must never become a
`score > X` gate. `min_cos` stays on the cosine, where it is today.

Winner rule as usual: the default flips only if it beats the current default
on the frozen eval set. A negative result is a real finding — that a term
match says little about relevance on short atomic fragments — and closes the
question instead of leaving it open.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Weighted min-max fusion is implemented alongside RRF in `_kbindex.py`, selectable for measurement without changing the default
- [ ] #2 Weights renormalise onto the arms that actually returned candidates, so a single-arm query is not scaled down
- [ ] #3 The eval harness reports both fusions on the memory layer and on wiki, at a semantic weight sweep of at least three points
- [ ] #4 `min_cos` continues to gate on cosine, never on the fused score; FTS-only hits keep their bypass
- [ ] #5 The default changes only on a win under the frozen-set winner rule; the outcome and the numbers are written up in docs/research/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->
