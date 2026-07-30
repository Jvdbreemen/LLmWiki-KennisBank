---
id: TASK-111
title: >-
  Figure spec: correct three factual claims about vault, indexes and Atlas
  lenses
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 05:42'
updated_date: '2026-07-30 17:54'
labels:
  - docs
  - c4
  - accuracy
dependencies: []
ordinal: 113700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The architecture-overview drawing specification states three things the repository contradicts. All three were established against source at v0.25.0. All three are confined to C4-Documentation/figure-spec-architecture-overview.md; no other document repeats them, so this is a single-file correction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 C6 S1 sublabel lists all ten numbered vault folders (00-inbox, 01-raw, 02-wiki, 03-projecten, 04-templates, 05-bronnen, 06-claude, 07-media, 08-archive, 09-memory) instead of the current five; the canonical list is verifiable in setup.sh
- [x] #2 C6 S2 note no longer claims all four databases rebuild: kb-usage.db is behavioural telemetry with no markdown ancestor and no rebuild path, unlike kb-index.db, kb-activity.db and kb-graph.db
- [x] #3 Part F item 3 and the Part H Mermaid label for S2 are reworded consistently with the corrected S2 note, so the spec does not contradict itself
- [x] #4 C7 R2 no longer names a timeline lens; the seven shipped lenses are named as overview, graph, wordcloud, time slider, memory health, recall and graphify
- [x] #5 The lens correction cites c4-code-atlas-frontend-src-lenses.md:37, which records that the Timeline lens was dropped, so a future reader can see the spec and the code-level docs now agree
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All three claims were confined to the figure spec, confirmed by grep across the repository before editing, so no other document needed touching. The lens correction is the strongest of the three: it did not merely disagree with the source tree, it disagreed with the repository's own code-level documentation, which records the Timeline lens as dropped under TASK-27.18 and its route, client method and bucket type as surviving dead code. The seven shipped lenses were read from atlas/frontend/src/lenses/ (overview, graph, wordcloud, time-slider, memory-health, recall, graphify) and cross-checked against c4-code-atlas-frontend-src-lenses.md:37. A short note after the C7 table now carries that citation so the name cannot drift back in from an older draft.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Corrects three factual claims in the architecture-overview drawing specification, each verified against source at v0.25.0.

The vault sublabel in C6 listed five numbered folders; setup.sh creates ten, so all ten are now named (00-inbox, 01-raw, 02-wiki, 03-projecten, 04-templates, 05-bronnen, 06-claude, 07-media, 08-archive, 09-memory).

The index note in C6 claimed all four SQLite databases rebuild. Three do. kb-usage.db is behavioural telemetry with no markdown ancestor and no rebuild path, so deleting it loses the history for good. The note, the matching accuracy constraint in Part F item 3, and the S2 label in the Part H Mermaid fallback are now consistent with each other.

The Atlas box in C7 named a timeline lens. No such lens exists: it was dropped under TASK-27.18 and the repository's own code-level documentation records the leftover route, client method and bucket type as dead code. The seven shipped lenses are now named, with a citation to c4-code-atlas-frontend-src-lenses.md:37 so the stale name cannot return.

Tests: tests/test_docs_consistency.py, 5 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
