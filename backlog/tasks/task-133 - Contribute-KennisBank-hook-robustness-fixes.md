---
id: TASK-133
title: Contribute KennisBank hook robustness fixes
status: Done
assignee: []
created_date: '2026-08-04 18:49'
updated_date: '2026-08-12 16:13'
labels: []
dependencies: []
references:
  - v0.28.0
modified_files:
  - scripts/_vaultpath.py
  - scripts/_embeddings.py
  - scripts/kb-retrieve.py
  - scripts/kb-session-start.py
  - scripts/memory-notify.py
priority: medium
ordinal: 128700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Isolate and contribute the fail-open vault path, embedding warm-worker liveness, retrieval warm marker, SessionStart environment propagation, and memory-notify worker-state fixes from the deployed local vault.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Five mapped tooling scripts are compared against the installed release baseline and only real upstream changes are included.
- [x] #2 The contribution branch is pushed and a PR targets the upstream main branch.
- [x] #3 No vault content, local path stamps, backups, or personal configuration are included.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Compare deployed tooling against v0.28.0; copy the five approved scripts; run focused syntax and hook checks; push a contribution branch and open a draft PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Landed in PR #103 (merge 33d1a2e / commit df2667e, 'fix(hooks): make Codex session start and worker locks reliable'), CI green. Follow-up filed separately: the worker-lock staleness rule itself was still wrong on Windows -- see TASK-140.
<!-- SECTION:NOTES:END -->
