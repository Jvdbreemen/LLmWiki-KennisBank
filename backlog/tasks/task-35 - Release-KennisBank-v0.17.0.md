---
id: TASK-35
title: Release KennisBank v0.17.0
status: Done
assignee: []
created_date: '2026-07-19 15:54'
updated_date: '2026-07-19 16:07'
labels: []
dependencies: []
modified_files:
  - CHANGELOG.md
  - README.md
  - README.nl.md
  - AGENTS.md
  - docs/copilot-headroom-evaluation.md
priority: high
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Promote the hookless Codex/Copilot integration and generated command-skill fix into the v0.17.0 minor release, align user-facing version documentation, validate the release state, and publish the tag/release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CHANGELOG contains a dated 0.17.0 section and correct compare links
- [x] #2 README release highlights identify v0.17.0 and explain the hookless Codex/Copilot command model
- [x] #3 Repository guidance no longer claims Codex or Copilot lifecycle hooks are installed
- [x] #4 Focused documentation and integration tests pass
- [x] #5 Changes are merged to main and GitHub release v0.17.0 is published
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Audit canonical release/version references. 2. Update CHANGELOG, README, and agent integration guidance. 3. Run focused tests and docs checks. 4. Commit, push, merge through PR, tag v0.17.0, and publish release. 5. Verify live upgrade discovery against the explicit Windows vault.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Release audit confirmed this project derives installed versions from Git tags rather than a package version constant. Added the dated v0.17.0 changelog section and compare links; refreshed English and Dutch README highlights; corrected the AGENTS.md hook contract and the superseded Headroom evaluation. Focused verification: 53 passed, 1 skipped.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Published LLmWiki-KennisBank v0.17.0 from merge commit 4bafcd5 after the full GitHub CI suite passed. Upgraded the explicit Windows vault D:/Users/Robert/Documents/Claude/Projects/Kluis with drift backups, stamped it v0.17.0, and verified Claude/Codex/Copilot integration with zero validation errors. Codex and Copilot contain zero KennisBank lifecycle-hook references and both sessiestart/sessielog skills are discoverable. Doctor still reports two pre-existing provenance-lint findings and 13 old unverified memories; these content-health findings are outside the release bump.
<!-- SECTION:FINAL_SUMMARY:END -->
