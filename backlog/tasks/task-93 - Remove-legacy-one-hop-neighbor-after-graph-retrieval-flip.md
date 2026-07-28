---
id: TASK-93
title: 'Remove legacy one_hop_neighbor one release after the graph_retrieval flip'
status: To Do
assignee: []
created_date: '2026-07-29 00:45'
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
- [ ] #1 One release shipped with graph_retrieval default ON and no regressions reported
- [ ] #2 one_hop_neighbor + legacy branch + tests removed; _neighbor_entry graph-only
- [ ] #3 Docs updated (CONFIGURATION, settings surfaces); suite green
<!-- AC:END -->
