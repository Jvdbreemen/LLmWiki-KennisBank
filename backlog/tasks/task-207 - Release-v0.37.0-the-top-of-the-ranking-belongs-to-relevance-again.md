---
id: TASK-207
title: >-
  Release v0.37.0 - the top of the ranking belongs to relevance again
status: Done
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
- [x] #1 CHANGELOG 0.37.0 section + compare links
- [x] #2 Both README highlight sections, one edit
- [x] #3 Combined-tree suite green (CI at ae4dff3) and docs subset green after the edit
- [x] #4 PR, CI green, review processed
- [x] #5 Merge verified on origin/main before tagging; tag equals that SHA
- [x] #6 Release published, non-empty body
- [x] #7 Tasks closed
<!-- AC:END -->

## Final Summary

v0.37.0 released. Tag on 4636a3e (= origin/main via rev-list before publish), body 2937 chars non-empty verified. Gate: combined-tree CI green at merge SHA ae4dff3 (Linux full suite), docs subset 56 passed after the edit. Copilot again absent upstream; the code carried its own second-reader coverage per PR.
