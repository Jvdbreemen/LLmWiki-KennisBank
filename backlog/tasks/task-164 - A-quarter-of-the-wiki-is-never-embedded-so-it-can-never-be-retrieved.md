---
id: TASK-164
title: 'A quarter of the wiki is never embedded, so it can never be retrieved'
status: Done
assignee: []
created_date: '2026-08-15 11:54'
labels: []
dependencies: []
priority: high
ordinal: 157700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_embeddings.doc_text` caps a document at 4000 characters before embedding it, and `get_cached` — the one path every wiki vector goes through — takes that default. Measured on the live vault:

    wiki    n=208   median 3344   p90 6397   max 58794   >4000: 74 (35.6%)
            never embedded: 23.1% of all wiki characters
    memory  n=2389  median 190    p90 250    max 378     >4000: 0

So a third of the articles are represented by their opening only, and just under a quarter of everything written in the wiki cannot be found by semantic recall at all. Not ranked low — absent. The longest article is 58794 characters and contributes 4000 of them. Memories are unaffected, which is why this never showed up in memory work.

It surfaced sideways. TASK-163 measured passage retrieval against ground truth from the extractor (255 claims, known originating chunk) and found that *granularity* was the whole problem: embedding every chunk instead of a shortlist gained nothing significant (46.3% vs 47.1% hit@1, p=0.39), while retrieving on 1500-character windows and handing back the containing chunk went from 43.5% to 63.5% hit@1 (p=3.3e-08) and 66.7% to 83.1% hit@2. One vector cannot represent 6000 characters of mixed subject matter, and the same argument applies with more force to a 58k-character article behind a 4000-character cap.

The likely fix has the same shape: index windows rather than documents, and return the document. That changes the cache's unit from one vector per file to several, so it touches `get_cached`, the cache format, and every caller that assumes one vector per path — which is why this is a task and not a patch.

Two things to establish before building anything, in this order:

1. **Does it actually cost recall?** Run kb-eval on the existing question sets against both indexing schemes. The cap has been there all along, so the current numbers already include the damage; only an A/B says how much of it is recoverable.
2. **What does it cost to build and hold?** Roughly 3-4x the vectors for the wiki. Cheap in absolute terms at this corpus size, but the recall path is the hot path and it stays sub-second only if the cost is paid at write time.

Do not skip step 1. TASK-145 pre-registered a rule that looked obviously right and lost (recall@5 0.778 → 0.768), and the pre-registration is the only reason that was reported rather than rationalised.</description>
<parameter name="acceptanceCriteria">["The recall cost of the 4000-character cap is measured with kb-eval on existing question sets, not assumed", "If windowed indexing wins, it wins on a pre-registered rule stated before the run", "Whatever the outcome, the numbers are written down — including a loss", "The hot path stays sub-second: any added cost is paid at write time", "python -m pytest tests -q is green"]</parameter>
<parameter name="labels">["retrieval", "embeddings", "measurement", "wiki"]
<!-- SECTION:DESCRIPTION:END -->
