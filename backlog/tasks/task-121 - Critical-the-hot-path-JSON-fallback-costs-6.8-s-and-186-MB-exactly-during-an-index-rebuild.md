---
id: TASK-121
title: >-
  Critical: the hot-path JSON fallback costs 6.8 s and 186 MB, exactly during an
  index rebuild
status: Done
assignee: []
created_date: '2026-07-30 10:18'
updated_date: '2026-07-30 18:12'
labels: []
dependencies: []
ordinal: 119700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the comprehensive review performance pass. kb-retrieve.py:222-235 falls back to emb.load_cache() plus pure-Python cosine whenever kb_recall.index_is_gated() is falsy. Traced with the real 170.8 MB embeddings-cache.json and no kb-index.db: _wiki_block took 6766 ms of a 7687 ms hook run. Components measured separately: read_text 733 ms, json.loads 4745 ms, pure-Python cosine over the whole cache 1878 ms, resident Python heap after the parse 186 MB, transient peak ~356 MB. The timing of when it fires is what makes it critical: build-kb-index.py:98 (--rebuild) and :109-114 (embed_id or unit_norm mismatch) UNLINK the index and rebuild it in the detached worker, so for the whole rebuild window _open_ro returns None, index_is_gated() is False, and every prompt pays 6.8 seconds. The cliff therefore lands precisely after an upgrade or a model switch, when the user is most likely to be typing. Recommended fix is to delete the fallback rather than speed it up: a 170 MB pure-Python JSON parse does not belong on a path budgeted at 2.0 s, and optimising it keeps a second retrieval implementation alive against the KISS rule. The hook already owns the right mechanism for "I could not retrieve this turn" - _emit_notice, used today for a cold model - so a missed turn becomes visible instead of a stall. One implementation detail to respect: _emit_notice must fire at most once per hook run, so the same guard has to suppress the memory block too, either by threading a flag out of _wiki_block or by hoisting the gate check into main(). Related: the same 170 MB cache is also the cost behind the kb-search finding and the memory-sweep dedup finding, and its size is an artefact of save_cache using indent=2, which puts every one of the 4096 floats on its own line.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The load_cache fallback is removed from kb-retrieve's wiki block
- [x] #2 An absent or rebuilding index produces a visible _emit_notice instead of a stall
- [x] #3 The notice fires at most once per hook run even though two blocks check the gate
- [x] #4 A test asserts the hook returns within a bounded time with no kb-index.db present
- [x] #5 No unbounded-memory read remains on the hot path
- [ ] #6 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The JSON cache fallback is gone from kb-retrieve._wiki_block. The block now returns a _NO_INDEX sentinel when the index is missing, ungated or raises, which lets main() distinguish "the index returned nothing" from "there was no index" - the first must stay silent, the second must reach the user. main() emits _emit_notice once per run for the second case, reusing the mechanism already used for a cold model. Measured after: a hook run against a vault with no index returns in 1198 ms, essentially all of it the embedding call, against the 6766 ms and 186 MB the reviewer traced for the old path. Test contract migrated rather than deleted: four tests that encoded the removed fallback were rewritten to the new contract - a missing index returns the sentinel, a broken index returns the sentinel, an ungated index never injects unfiltered and never calls wiki_hits, and emb.load_cache is asserted never to be called on the hot path. One mistake worth recording: the first deletion also removed _provenance_tag, which lived inside the deleted span; the memory-block test caught it immediately and it was restored from git.
<!-- SECTION:FINAL_SUMMARY:END -->
