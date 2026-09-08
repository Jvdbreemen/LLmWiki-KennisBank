---
id: TASK-239
title: Enforce the experience projection build capability before rebuild work
status: In Progress
assignee:
  - '@codex'
created_date: '2026-09-08 05:06'
updated_date: '2026-09-08 05:10'
labels:
  - experience-memory
  - production
  - safety
dependencies: []
priority: high
type: bug
ordinal: 178600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The production rebuild CLI ignored experience_projection and could initialize the optional backend and build a projection while the selected vault did not grant build authority. Restore the preregistered capability boundary before any backend/storage work without changing internal deterministic builder APIs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tests first demonstrate that a missing, false, corrupt or legacy-only capability cannot initialize embeddings or call the projection builder
- [x] #2 The rebuild CLI checks experience_projection in the selected vault before any optional backend or storage work
- [x] #3 Explicit vault authority is honored and missing vault configuration fails safely instead of using the working directory
- [ ] #4 An enabled capability preserves split-store rebuild and lexical fallback behavior; focused tests and current full-suite evidence are recorded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add negative capability and same-vault regression tests and observe failure. 2. Gate CLI before optional embedding/backend resolution, keeping internal pure builder usable by tests. 3. Verify enabled behavior, update command instructions and per-task evidence. 4. Integrate with full production regressions before release.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Test-first proof: four new tests failed with status ok instead of disabled or exit 0 instead of invalid; two enabled-path controls passed. Same-vault gate then made the focused policy suite pass (27/27); real subprocess denial/preservation and enabled lexical rebuild tests added subsequently.
<!-- SECTION:NOTES:END -->
