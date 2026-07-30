---
id: TASK-122
title: Release v0.26.1
status: In Progress
assignee:
  - '@claude'
created_date: '2026-07-30 19:01'
updated_date: '2026-07-30 19:01'
labels:
  - release
dependencies: []
ordinal: 117700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Patch release carrying documentation-only corrections to the C4 architecture set that shipped in v0.26.0. Carries TASK-111 (three factual claims in the figure spec: vault folder count, database rebuildability, a named Atlas lens that does not exist), TASK-112 (two geometry errors and a wrong internal cross-reference in the same spec), TASK-113 (a seven-component contradiction between the figure spec and c4-component.md), and TASK-114 (review of the automated container and context revisions, which restored claude-cli to the documented consent boundary). Patch rather than minor: no code, schema, output contract or dependency changes, only documentation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The full suite runs before the release documentation is written, and any failure is either fixed or shown to be the known Windows-only test_setup_deploy.py flake recorded in TASK-116
- [ ] #2 CHANGELOG.md carries a dated 0.26.1 section and both compare links at the bottom are updated
- [ ] #3 README.md and README.nl.md are updated together in the same commit, never one without the other
- [ ] #4 The documentation subset gate passes after the changelog and README edits
- [ ] #5 A pull request is opened against origin/main, CI is green, and every Copilot review comment is checked against the code rather than dismissed
- [ ] #6 The tag is placed on a SHA verified to be on origin/main after the merge, not on a branch tip
- [ ] #7 The published release body is verified non-empty
<!-- AC:END -->
