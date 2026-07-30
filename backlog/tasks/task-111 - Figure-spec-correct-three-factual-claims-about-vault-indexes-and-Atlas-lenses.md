---
id: TASK-111
title: >-
  Figure spec: correct three factual claims about vault, indexes and Atlas
  lenses
status: To Do
assignee: []
created_date: '2026-07-30 05:42'
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
- [ ] #1 C6 S1 sublabel lists all ten numbered vault folders (00-inbox, 01-raw, 02-wiki, 03-projecten, 04-templates, 05-bronnen, 06-claude, 07-media, 08-archive, 09-memory) instead of the current five; the canonical list is verifiable in setup.sh
- [ ] #2 C6 S2 note no longer claims all four databases rebuild: kb-usage.db is behavioural telemetry with no markdown ancestor and no rebuild path, unlike kb-index.db, kb-activity.db and kb-graph.db
- [ ] #3 Part F item 3 and the Part H Mermaid label for S2 are reworded consistently with the corrected S2 note, so the spec does not contradict itself
- [ ] #4 C7 R2 no longer names a timeline lens; the seven shipped lenses are named as overview, graph, wordcloud, time slider, memory health, recall and graphify
- [ ] #5 The lens correction cites c4-code-atlas-frontend-src-lenses.md:37, which records that the Timeline lens was dropped, so a future reader can see the spec and the code-level docs now agree
<!-- AC:END -->
