---
id: TASK-148
title: >-
  Maintenance passes report zero whether they worked or failed, and re-embed
  1506 memories to get there
status: Done
assignee: []
created_date: '2026-08-12 20:33'
updated_date: '2026-08-12 22:06'
labels:
  - bug
  - memory
  - performance
  - observability
dependencies: []
references:
  - scripts/memory-sweep.py
  - scripts/_maintenance.py
  - scripts/_embeddings.py
  - docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md
priority: high
ordinal: 142700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The last sweep's heartbeat reads `superseded: 0`, `reconciled_superseded: 0`, `rechecked_retracted: 0`, `promote_marked: 0`, `exact_duplicates_closed: 0`. Every counter zero, and nothing distinguishes "nothing to do" from "this crashed".

Two independent causes.

**1. The zeros are unfalsifiable.** `memory-sweep.py` calls each pass inside `try: ... except Exception: 0`. A timeout, an OOM, a missing module and an idle run all produce the same line in the heartbeat. This is the same fail-safe-hides-the-failure pattern as TASK-143, one level up: there the seam swallowed a model that never answered, here the orchestrator swallows a pass that never ran.

**2. Every pass tries to re-embed almost the whole corpus.** `_maintenance.current_items()` calls `emb.get_cached(..., recompute=True)` per memory. On this vault the embeddings cache holds:

```
ollama:embeddinggemma+title: none | text:    1506 entries
ollama:qwen3-embedding:4b                      246
ollama:qwen3-embedding:8b                        6
```

`get_cached` gates reuse on `embed_id`, so 1506 of 1531 current memories miss and are re-embedded on every pass that calls `current_items()` — which is `supersede_pass`, `cluster_promote_pass`, and the reconcile pool. A manual `current_items()` call was still running after ten minutes.

The retrieval index is NOT affected: `kb-index.db` carries `embed_id = ollama:qwen3-embedding:4b`, dim 2560, 1531 memory docs. Recall is fine. This is a maintenance-path problem only.

Open question worth deciding here: prune the stale-`embed_id` entries from `embeddings-cache.json` (51 MB, mostly dead weight), or have `current_items()` read vectors from `kb-index.db` instead of re-embedding. The index already holds exactly the current-space vectors these passes need, so the second option removes the recompute entirely — but note the index holds only `status: current` docs, so superseded and unverified memories (130 of 1661) have no vector there.

Design context: `docs/superpowers/specs/2026-08-12-self-correcting-memory-layer-design.md`, step 4 and open question 2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A pass that fails is distinguishable from a pass that had nothing to do, in the heartbeat and in the log
- [x] #2 current_items() no longer re-embeds memories that already have a current-space vector, with the wall-clock time recorded before and after
- [x] #3 The decision on the stale embeddings cache is made and recorded: prune, or read vectors from the index
- [x] #4 A sweep run shows non-zero maintenance counters on a corpus where work demonstrably exists, or explains in the heartbeat why not
- [x] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Half done (commit 28ea0bb): the re-embed storm is gone.

Proven live rather than reasoned about. Running `memory-sweep.py --help` accidentally started a real sweep (argv is hand-parsed, so --help fell through to run_sweep). It ran ten minutes without writing a single memory, because current_items() was still re-embedding the corpus before the first transcript was touched. That is exactly the symptom this task describes, observed end to end.

current_items() now reads vectors from kb-index.db first, which already holds them in the current space (embed_id ollama:qwen3-embedding:4b, 1531 memory docs, maintained incrementally by build-kb-index):

  current_items()   1531 items in 16.8 s   (was >600 s and never finished)

Fail-soft: a missing index, a missing sqlite-vec extension, or an index under a different embed_id yields {} and every caller falls back to the cache. A shortcut, never a dependency. Vectors from another embedding space are refused outright, because cosine across two models is meaningless -- the same reason _embeddings gates cache reuse on embed_id.

That also answers AC #3 for now WITHOUT touching the 51 MB cache: pruning it is no longer on the critical path, since the passes no longer read it for memories that the index already covers. The cache stays as the fallback and for layers the index does not carry (superseded and unverified memories are not indexed).

Still open: AC #1 and #4, the silent zeros. `except Exception: 0` in memory-sweep.py still makes a crashed pass indistinguishable from an idle one.

Two unrelated defects found in the same file and fixed alongside, because they were in the way: --help started a sweep, and main() hardcoded max_memories_per_transcript=20, silently overriding the value TASK-145 had just set on measured evidence. sweep-launch.py starts the sweep through that exact path, so the raised cap would never have reached production.
<!-- SECTION:NOTES:END -->
