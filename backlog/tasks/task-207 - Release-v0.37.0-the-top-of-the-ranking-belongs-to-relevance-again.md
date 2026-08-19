---
id: TASK-207
title: >-
  Release v0.37.0 - the top of the ranking belongs to relevance again
status: In Progress
assignee: []
created_date: '2026-08-19 21:00'
labels:
  - release
ordinal: 172700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut v0.37.0 from origin/main at 2f0c5a6 (after merges #147, #148, #149, #150).

Carries: TASK-202 (per-client freshness gate), TASK-201 (shared current_focus
block), TASK-203 (cosine relevance term + minmax wiki fusion, defaults flipped
under the owner-amended ordering-class winner rule), and ADR-009 (embedding
default to qwen3-embedding:4b, from the parallel session).

Minor: new knobs (memory_fusion, wiki_fusion, KB_VERIFY knobs' siblings), a
new notification job (focus-notify.py), a new state file shape
(kb-session-start-state.json gains a clients map), and changed retrieval
defaults - all changed or new contracts.

Gate note: the three PR branches were each tested separately; the combined
tree's full suite ran green on CI at the exact merge SHA ae4dff3 (Linux
runner), which serves as gate run 1. The docs subset runs after the
changelog/README edit as usual.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CHANGELOG 0.37.0 section + compare links
- [ ] #2 Both README highlight sections, one edit
- [ ] #3 Combined-tree suite green (CI at ae4dff3) and docs subset green after the edit
- [ ] #4 PR, CI green, review processed
- [ ] #5 Merge verified on origin/main before tagging; tag equals that SHA
- [ ] #6 Release published, non-empty body
- [ ] #7 Tasks closed
<!-- AC:END -->
