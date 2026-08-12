---
id: TASK-134
title: >-
  Measure an L2 scene layer for memory retrieval (three clusterers, staged
  experiment)
status: In Progress
assignee: []
created_date: '2026-08-05 21:20'
updated_date: '2026-08-10 22:30'
labels:
  - retrieval
  - research
  - memory
dependencies: []
references:
  - docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md
  - docs/research/embedding-model-sweep-2026-08.md
  - 'https://github.com/TencentCloud/TencentDB-Agent-Memory'
priority: medium
ordinal: 129700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a scenario tier (L2) between atomic memories and curated wiki articles, modelled on TencentDB Agent Memory's L0-L3 pyramid, and measure whether it improves memory-layer recall.

Scenes are derived index rows in a new kb-scene.db, never vault markdown, and are never returned as retrieval hits — they act only as a prior that lowers the similarity floor and/or boosts the score of members of the winning scene.

Three clusterers behind one interface (graph community, tags+time-window, LLM with capacity cap) are compared in a staged experiment against an unmodified `main` baseline, using the existing kb-eval harness on the 1224-question memory eval set with a dev/holdout split plus an independent v2 confirmation set.

Design: docs/superpowers/specs/2026-08-05-l2-scene-retrieval-design.md

Out of scope (separate projects): in-session tool-payload compression, periodic re-derivation drift audit. Token count is not a metric — top_n is fixed, so injected block size is constant by construction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Parity: with the clusterer switched off, the worktree returns byte-identical memory hits to the `main` baseline, proven by a test
- [x] #2 kb-scene.db builds from existing kb-index.db embeddings without issuing any new embedding call
- [x] #3 Scenes are never returned as retrieval hits; the eval gold set is unchanged
- [x] #4 Fail-open: a missing or stale kb-scene.db behaves exactly like baseline, with no notice and no added latency
- [x] #5 scene_floor, scene_boost and scene_clusterer are resolved in kb-retrieve.retrieve_params() so kb-eval measures the same knobs as the hook
- [x] #6 Scene diagnostics (count, size distribution, coverage, singleton share) and the oracle ceiling are reported per clusterer before its retrieval run
- [ ] #7 Stage 1 compares all three clusterers at a fixed neutral prior; stage 2 sweeps the prior on the two best only
- [x] #8 Winner rule applied as specified: recall@5 >= +0.02, recall@1 not lower, p50 latency +<5ms, gain in >=2 of 4 memory_type groups
- [x] #9 Holdout (30% split) and kb-memory-eval-set-v2.json each run exactly once, on the chosen configuration only
- [x] #10 Report written to docs/research/l2-scene-retrieval-2026-08.md with per-arm tables, twenty flip examples in each direction, raw JSON alongside, and an explicit conclusion including what did not work
- [x] #11 scene_retrieval toggle defaults to off and is only enabled if the winner rule is met
- [ ] #12 python -m pytest tests -q is green
<!-- AC:END -->



## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measured 2026-08-10/11. Verdict: no arm met the winner rule; scene_retrieval stays off. Full report: docs/research/l2-scene-retrieval-2026-08.md.

AC verdicts that are not a plain tick:
- AC #1 (parity): satisfied by tests, not by a pinned run against `main`. tests/test_scene_recall.py::test_no_prior_never_consults_the_scene_store proves the off state never touches kb-scene.db, and ::test_baseline_rows_are_a_prefix_of_the_result proves the prior only appends. The empirical `--no-prior` arm reproduced baseline exactly (0 flips across two runs).
- AC #7 (three clusterers at a neutral prior): DEVIATION. Only `community` produced a scene index. `tags` yields 0 scenes because 0 of 1620 memory files carry a non-empty tags field. `llm` yields 0 scenes because gemma4:12b answers a 32k-token, 1508-id prompt with 3100 characters of Dutch prose containing no JSON. Both are recorded with evidence rather than ticked.
- AC #8 (winner rule): applied, all four conditions fail on the best arm (recall@5 +0.000, recall@1 -0.006, p50 +65ms, 1 of 4 memory_type groups).
- AC #9: satisfied vacuously. No winner, so the holdout split and kb-memory-eval-set-v2.json were deliberately NOT run and remain unspent for future work.

Bug fixed on this branch: build-scene-index.py called _llm.complete, which does not exist (_llm exposes generate). That was an AttributeError, not a fail-open path.

Side finding, filed as TASK-136: turning off embed_index/memory_capture makes build-kb-index prune the entire derived index (1707 documents deleted). Three arms ran against an empty index and produced plausible-looking negatives before the cause was found.
<!-- SECTION:NOTES:END -->
