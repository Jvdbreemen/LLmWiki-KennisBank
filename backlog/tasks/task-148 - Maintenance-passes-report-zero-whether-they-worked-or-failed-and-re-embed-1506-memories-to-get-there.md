---
id: TASK-148
title: >-
  Maintenance passes report zero whether they worked or failed, and re-embed
  1506 memories to get there
status: To Do
assignee: []
created_date: '2026-08-12 20:33'
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
- [ ] #1 A pass that fails is distinguishable from a pass that had nothing to do, in the heartbeat and in the log
- [ ] #2 current_items() no longer re-embeds memories that already have a current-space vector, with the wall-clock time recorded before and after
- [ ] #3 The decision on the stale embeddings cache is made and recorded: prune, or read vectors from the index
- [ ] #4 A sweep run shows non-zero maintenance counters on a corpus where work demonstrably exists, or explains in the heartbeat why not
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->
