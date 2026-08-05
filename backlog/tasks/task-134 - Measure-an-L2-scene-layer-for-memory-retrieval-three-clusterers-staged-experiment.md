---
id: TASK-134
title: >-
  Measure an L2 scene layer for memory retrieval (three clusterers, staged
  experiment)
status: In Progress
assignee: []
created_date: '2026-08-05 21:20'
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
- [ ] #1 Parity: with the clusterer switched off, the worktree returns byte-identical memory hits to the `main` baseline, proven by a test
- [ ] #2 kb-scene.db builds from existing kb-index.db embeddings without issuing any new embedding call
- [ ] #3 Scenes are never returned as retrieval hits; the eval gold set is unchanged
- [ ] #4 Fail-open: a missing or stale kb-scene.db behaves exactly like baseline, with no notice and no added latency
- [ ] #5 scene_floor, scene_boost and scene_clusterer are resolved in kb-retrieve.retrieve_params() so kb-eval measures the same knobs as the hook
- [ ] #6 Scene diagnostics (count, size distribution, coverage, singleton share) and the oracle ceiling are reported per clusterer before its retrieval run
- [ ] #7 Stage 1 compares all three clusterers at a fixed neutral prior; stage 2 sweeps the prior on the two best only
- [ ] #8 Winner rule applied as specified: recall@5 >= +0.02, recall@1 not lower, p50 latency +<5ms, gain in >=2 of 4 memory_type groups
- [ ] #9 Holdout (30% split) and kb-memory-eval-set-v2.json each run exactly once, on the chosen configuration only
- [ ] #10 Report written to docs/research/l2-scene-retrieval-2026-08.md with per-arm tables, twenty flip examples in each direction, raw JSON alongside, and an explicit conclusion including what did not work
- [ ] #11 scene_retrieval toggle defaults to off and is only enabled if the winner rule is met
- [ ] #12 python -m pytest tests -q is green
<!-- AC:END -->
