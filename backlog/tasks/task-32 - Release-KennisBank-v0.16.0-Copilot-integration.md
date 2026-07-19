---
id: TASK-32
title: Release KennisBank v0.16.0 Copilot integration
status: Done
assignee:
  - Codex
created_date: '2026-07-19 07:48'
updated_date: '2026-07-19 07:58'
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
- [x] #2 The repository CI passes for the release commit.
- [x] #3 The release commit is merged to upstream main through a GitHub pull request.
- [x] #4 Annotated tag v0.16.0 and a GitHub Release are published on the upstream repository.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add the skill-frontmatter fix to the existing Unreleased Copilot notes and roll them into v0.16.0. 2. Run focused and CI-equivalent validation. 3. Push a fork branch, open and merge an upstream release PR. 4. Tag the merged upstream commit and publish GitHub release notes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Prepared v0.16.0 changelog by rolling the existing Copilot CLI integration notes out of Unreleased and adding the Copilot skill-frontmatter fix. Local validation: 15 focused skill/installer tests passed; all Python scripts compile; setup.sh and doctor.sh pass bash syntax checks; git diff check passed.

GitHub release evidence: fix PR #35 and release PR #36 merged; both CI runs passed; annotated tag v0.16.0 points to merged upstream main commit 01fc6c10214e7e27f7d30673fdc9b935b8bd044b; release published at https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.16.0.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released KennisBank v0.16.0 with the opt-in GitHub Copilot CLI integration and the repaired personal-skill YAML frontmatter. Both implementation and release PRs passed CI and merged upstream; annotated tag v0.16.0 and user-facing GitHub Release notes are published.
<!-- SECTION:FINAL_SUMMARY:END -->
