---
id: TASK-136
title: Turning off an index toggle prunes the derived index instead of freezing it
status: Done
assignee: []
created_date: '2026-08-10 22:09'
updated_date: '2026-08-13 05:37'
labels:
  - bug
  - index
  - retrieval
dependencies: []
references:
  - scripts/build-kb-index.py
  - scripts/_kbindex.py
priority: high
ordinal: 130700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`build-kb-index.py::_collect()` gates each layer on a settings toggle:

```python
if _settings.get("embed_index", True) and WIKI.exists():   # wiki layer
if _settings.get("memory_capture", True) and MEMORY.exists():  # memory layer
```

and `main()` then calls `_kbindex.prune(conn, keep_paths=seen)`. With a toggle off, that layer contributes nothing to `seen`, so `prune` reads its documents as "no longer on disk" and deletes every row for that layer from `docs`, `fts_docs`, `vec_docs` and `doc_sources`.

Observed on 2026-08-10 while pausing background automation for the TASK-134 measurement:
- `embed_index=false` -> next index run removed all 199 wiki documents.
- `memory_capture=false` -> next run removed the remaining 1508 memory documents, leaving `docs` at 0 rows in a 23 MB file.
- Retrieval then silently returned nothing relevant; the eval arms that ran against it scored recall 0.016, 0.000, 0.000 and looked like a genuine negative result.

Recovery was possible from `embeddings-cache.json` (1707 documents, 0 failed, no model calls), but only because the cause was known. The user-visible failure mode is "search stopped working" with no notice and no log line.

The toggles are documented as pausing background work, not as scope declarations for the index. "Do not index new or changed files" and "consider these files deleted" must not share a code path.

Suggested direction: prune only within the layers that were actually collected (scope the keep-set per layer), or skip pruning entirely when any layer is toggled off, and log the removal count when a run deletes more than a small fraction of the index.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A regression test proves that running build-kb-index with embed_index=false leaves existing wiki rows in the index
- [x] #2 A regression test proves that running build-kb-index with memory_capture=false leaves existing memory rows in the index
- [x] #3 A run that prunes more than 10% of the index reports the removal count on stderr instead of removing silently
- [x] #4 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed in three parts, plus a fourth defect found on the way.

1. `_kbindex.prune()` takes a `layers` argument and only judges the layers the run actually read. Without it, a layer that was not collected has an empty keep-set and every one of its documents reads as deleted. Omitting the argument keeps the old behaviour, so other callers are untouched.

2. `_active_layers()` is split out of `_collect()`. Two places need to know which layers are in scope -- the collector and the prune -- and keeping that knowledge inside the collector is exactly how 'index nothing new from this layer' and 'treat this layer as gone' ended up sharing a code path.

3. Not in the task: the early-exit staleness probe compared `count(*) FROM docs` against the keep-set. With a toggle off, the frozen layer is in `docs` but not in `seen`, so that check reported stale forever and every session start ran a full pass for nothing. Now counted per active layer.

4. The notice. The removal count was already printed -- as one number among five on the closing line. That is how 199 wiki documents and then 1508 memory documents disappeared unnoticed: the line reported it, and reported it as routine. `prune_notice()` now writes an explicit warning to stderr above a tenth of the index, naming the layers the run read. Below that it stays quiet, because a warning that fires on ordinary housekeeping teaches you to ignore it.

Ten tests, including the inverse: a genuinely deleted file is still removed, with its rows in fts_docs, vec_docs and doc_sources. The scope narrows the judgement; it does not switch pruning off.

Gate: python -m pytest tests -q -> 1261 passed, 2 skipped.
<!-- SECTION:NOTES:END -->
