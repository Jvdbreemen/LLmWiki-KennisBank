---
id: TASK-32
title: Release KennisBank v0.16.0 Copilot integration
status: In Progress
assignee:
  - Codex
created_date: '2026-07-19 07:48'
updated_date: '2026-07-19 07:50'
labels:
  - release
  - copilot
dependencies:
  - TASK-31
documentation:
  - CHANGELOG.md
modified_files:
  - CHANGELOG.md
priority: high
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Publish the merged GitHub Copilot CLI integration and the skill-frontmatter repair as KennisBank v0.16.0, using a release PR, annotated tag, and GitHub Release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CHANGELOG rolls the current Copilot integration notes into v0.16.0 and includes the skill parsing fix.
- [ ] #2 The repository CI passes for the release commit.
- [ ] #3 The release commit is merged to upstream main through a GitHub pull request.
- [ ] #4 Annotated tag v0.16.0 and a GitHub Release are published on the upstream repository.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add the skill-frontmatter fix to the existing Unreleased Copilot notes and roll them into v0.16.0. 2. Run focused and CI-equivalent validation. 3. Push a fork branch, open and merge an upstream release PR. 4. Tag the merged upstream commit and publish GitHub release notes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Prepared v0.16.0 changelog by rolling the existing Copilot CLI integration notes out of Unreleased and adding the Copilot skill-frontmatter fix. Local validation: 15 focused skill/installer tests passed; all Python scripts compile; setup.sh and doctor.sh pass bash syntax checks; git diff check passed.
<!-- SECTION:NOTES:END -->
