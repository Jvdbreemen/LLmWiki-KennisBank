---
id: TASK-93
title: Remove legacy one_hop_neighbor one release after the graph_retrieval flip
status: Done
assignee: []
created_date: '2026-07-29 00:45'
updated_date: '2026-08-03 21:26'
labels:
  - retrieval
  - cleanup
dependencies:
  - TASK-87
ordinal: 96700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-87 flipped `graph_retrieval` to ON after the A/B gate passed
(329-question set: @1 0.745->0.790, @5 ->1.000, single-hop@1 +5.4pt). The
legacy regex expansion (`_rank.one_hop_neighbor` + its tests) stays as the
toggle-off fallback for exactly one release, then gets removed: keeping two
neighbor sources indefinitely is the kind of dual-path drift TASK-15 warns
about. Removal = delete `one_hop_neighbor`, simplify `_neighbor_entry` to the
graph path (toggle then only gates expansion on/off), drop the legacy branch
tests, update CONFIGURATION/settings docs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One release shipped with graph_retrieval default ON and no regressions reported
- [x] #2 one_hop_neighbor + legacy branch + tests removed; _neighbor_entry graph-only
- [x] #3 Docs updated (CONFIGURATION, settings surfaces); suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
graph_retrieval shipped default ON in v0.25.0; four releases (v0.26.0, v0.26.1, v0.27.0, v0.28.0) ran on it with no reported regression, satisfying AC#1.

Removed: `_rank.one_hop_neighbor` (and its now-unused `_WIKILINK_RE`/`Counter` imports), the `TestOneHopNeighbor` class in tests/test_rank.py, the `RankIsolatieTest` class in tests/test_graph_provenance_ring.py (the property it guarded -- a neighbor can never be a session log -- now holds structurally: .graphifyignore excludes 01-raw/sessies entirely, so such a node cannot exist in kb-graph.db, which is a stronger guarantee than the old runtime filter).

`_neighbor_entry` in kb-recall.py no longer selects between two implementations; `graph_retrieval` is now a pure on/off switch for the graph-neighbor lookup, with no fallback. Toggle tests in test_graph_retrieval.py rewritten to match: off now asserts no entry, on asserts the graph path, both without patching a deleted function.

CONFIGURATION.md's graph_retrieval row corrected (no more "legacy wikilink-scan" claim for the off state). README.md/README.nl.md's one-line settings-table entries made no claim about the off-state implementation, so needed no change.

Bonus finding while in tests/test_rank.py: an `if __name__ == "__main__": unittest.main()` sat mid-file, before two more test classes -- the same "tests silently skipped under direct execution" bug class found earlier in statusline.sh today. Fixed by moving it to the true end of the file.

Full suite: 1129 passed, 2 skipped.
<!-- SECTION:FINAL_SUMMARY:END -->
