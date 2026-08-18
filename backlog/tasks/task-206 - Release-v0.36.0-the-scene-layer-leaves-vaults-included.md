---
id: TASK-206
title: 'Release v0.36.0 - the scene layer leaves, vaults included'
status: Done
assignee: []
created_date: '2026-08-18 21:35'
labels:
  - release
dependencies: []
priority: high
type: chore
ordinal: 171700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut v0.36.0 from origin/main at e757feb (merge of PR #145).

Carries TASK-205: removal of the L2 scene retrieval layer after its measured rejection (TASK-134), recorded as ADR-008, plus the version-gated migration `0.36.0 scene-laag-opruimen` that prunes the four stale scripts and kb-scene.db from deployed vaults.

Minor, not patch, despite chore:/fix: commit labels: removes the `scene_retrieval` toggle, the `scene_clusterer`/`scene_floor`/`scene_boost` knobs, the `KB_SCENE_*` env vars, and prunes files from deployed vaults - changed contracts. `_migrations.VERSION` is already stamped 0.36.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CHANGELOG.md carries a dated [0.36.0] section and both compare links are updated
- [x] #2 README.md and README.nl.md highlight sections updated in the same edit
- [x] #3 Full suite green before the docs edit; documentation subset green after
- [x] #4 PR against origin/main, CI green, review processed (Copilot if it appears; it has been silent upstream since #137)
- [x] #5 Merge verified on origin/main before tagging; tag equals that SHA via git rev-list -n1
- [x] #6 Release published with a non-empty body
- [x] #7 This task and TASK-205 administration closed
<!-- AC:END -->

## Final Summary

v0.36.0 released. Tag on c76f124 (merge of PR #146), verified equal to
origin/main via rev-list before publishing. Release body 3136 chars,
non-empty verified. Gate: full suite 1587/3 via tree-identity with the
reviewed #145 head, docs subset 56 passed after the docs edit. Copilot
absent upstream (silent since #137); the code was second-reader-reviewed
on #145 with 9 findings fixed. Carries TASK-205 and migration
0.36.0 scene-laag-opruimen.
