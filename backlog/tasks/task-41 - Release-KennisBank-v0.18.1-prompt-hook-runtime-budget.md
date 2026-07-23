---
id: TASK-41
title: Release KennisBank v0.18.1 prompt-hook runtime budget
status: In Progress
assignee: []
created_date: '2026-07-23 22:28'
updated_date: '2026-07-23 22:30'
labels:
  - release
  - hooks
  - reliability
dependencies: []
modified_files:
  - CHANGELOG.md
  - README.md
  - README.nl.md
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Publish a patch release containing the UserPromptSubmit hard runtime ceiling from PR #49 on top of v0.18.0, with accurate release metadata, a verified main commit, annotated tag, and GitHub release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 PR #49 is merged into main with its required CI check green.
- [x] #2 CHANGELOG.md, README.md, and README.nl.md describe v0.18.1 without overstating changes already shipped in v0.18.0.
- [ ] #3 The release commit passes repository CI on main.
- [ ] #4 Annotated tag v0.18.1 and a non-draft, non-prerelease GitHub release point to the verified main commit.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Merge PR #49; update patch-release metadata on a release branch; verify locally and in CI; merge the release PR; create and push an annotated v0.18.1 tag; publish and verify the GitHub release.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #49 merged as 3e94fa0 after its required GitHub CI job passed. Release metadata is being prepared from origin/main on release/v0.18.1.

Release notes distinguish the v0.18.1 hard ceiling from v0.18.0 single-embed/pre-warm behavior. Focused release regression slice passed: 39 passed, 1 skipped with hostile inherited timeout values.
<!-- SECTION:NOTES:END -->
