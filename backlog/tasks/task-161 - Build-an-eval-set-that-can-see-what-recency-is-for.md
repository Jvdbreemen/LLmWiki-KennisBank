---
id: TASK-161
title: Build an eval set that can see what recency is for
status: To Do
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
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The set contains questions whose correct answer is the newest of several matching memories, and questions where it is an older one
- [ ] #2 Pairs derived from superseded_by are hand-checked, because those links record housekeeping as often as replacement
- [ ] #3 The set is held out from any tuning it is used to justify
- [ ] #4 Running the existing arms against it reports whether recency helps, hurts or does nothing on the case it exists for
- [ ] #5 The construction is documented well enough that someone can say what the set can and cannot measure
- [ ] #6 python -m pytest tests -q is green
<!-- AC:END -->
