---
id: TASK-161
title: Build an eval set that can see what recency is for
status: Done
assignee: []
created_date: '2026-08-14 06:02'
labels:
  - retrieval
  - research
  - memory
  - eval
dependencies: []
priority: high
ordinal: 154700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two measurements now say the ranking factors cost recall (TASK-138, TASK-160), and both are unactionable for the same reason: the eval set cannot see the case the factors were built for.

`kb-memory-eval-set.json` was generated one question per document. Each question is a paraphrase of the memory it is expected to retrieve, so the right answer is by construction the most semantically similar one. A ranking that prefers a fresher memory over a better-worded older one is penalised every single time, whether or not the fresher memory was actually the better answer.

So the current position is: recency costs 0.147 of recall@1 on a metric that would report exactly that even if recency were working perfectly. Nothing can be decided from it.

What a freshness-aware set needs, and it is a different construction rather than more of the same:

- Questions whose correct answer is the **newest** of several memories that all match the words. The vault has these — the supersede work found memories captured twice weeks apart, and pairs where a value changed (`qwen3-embedding:8b` then `4b`, a threshold moved, a decision reversed).
- Questions whose correct answer is the **older** one, so the set can also catch a recency weight that has gone too far. A set that only rewards freshness would licence any amount of it.
- The `superseded_by` links are a ready-made source for the first kind: a closed memory and its successor are, by definition, two memories about one subject where the newer is right. Note the contamination TASK-156 measured — many of those links record duplicate cleanups rather than replacements — so pairs need the same hand-labelling that task used.

Only with such a set does the tuning question become answerable: `RECENCY_FLOOR = 0.6` permits a 40% swing against RRF gaps of 1.6%, and the question is whether raising the floor keeps the preference for fresh knowledge while stopping it from overwriting the ranking.

Until then, do not change `_rank`. Two reports say what the current metric measures; none says what the user needs.

## Where the acceptance criteria stand

Evidence: `docs/research/freshness-eval-2026-08-16.md`. Set installed at
`06-claude/kb-freshness-eval.{dev,holdout}.json` (vault, not repo — eval
privacy guard).

- #1 met: 25 newest-wins and 64 oldest-wins questions, from 237 hand-labelled
  supersession pairs (145 DUPLICATE dropped — confirming TASK-156's
  contamination finding at scale).
- #2 met: every REPLACED/NARROWED skeptic-verified; five disputes adjudicated
  against code, not preference. A batching fault triple-labelled one batch,
  yielding free inter-rater data: 13/17 unanimous, 3 at 2-1, 1 three-way.
- #3 met: 45-question holdout written and never run.
- #4 met, with a twist. newest-wins: production 0.286 r@1 vs cosine 0.357,
  paired 2-1, p=1.0 — recency does not beat cosine on its own home ground
  (n=14, direction only). oldest-wins: 0.000 in BOTH arms, because
  `recall_hits` filters status=current and every expected answer is
  superseded. The brake question cannot be measured; what it exposed instead
  is TASK-169.
- #5 met: construction, limits and the adjudication protocol in the report.
- #6: suite untouched by this work (research doc + vault data only); last
  full run green at 1430.

**The set's oldest-wins half doubles as the regression gate for TASK-169**: it
scores zero by construction until a NARROWED-aware supersede lands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The set contains questions whose correct answer is the newest of several matching memories, and questions where it is an older one
- [x] #2 Pairs derived from superseded_by are hand-checked, because those links record housekeeping as often as replacement
- [x] #3 The set is held out from any tuning it is used to justify
- [x] #4 Running the existing arms against it reports whether recency helps, hurts or does nothing on the case it exists for
- [x] #5 The construction is documented well enough that someone can say what the set can and cannot measure
- [x] #6 python -m pytest tests -q is green
<!-- AC:END -->
