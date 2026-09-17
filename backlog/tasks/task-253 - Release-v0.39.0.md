---
id: TASK-253
title: Release v0.39.0
status: Done
assignee: []
created_date: '2026-09-17 20:45'
updated_date: '2026-09-17 21:03'
labels:
  - release
dependencies: []
ordinal: 191600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut v0.39.0 from main: explicit source and experience recall (PR #168, ADR-010), the single-flight sweep lock (ADR-011), research tools out of the vault deploy (ADR-012, TASK-252), the auto-crosslink fix (#171) and the contributed tooling (#169). 0.38.0 was never tagged; its schema step is part of this release.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CHANGELOG has a dated 0.39.0 section and updated compare links
- [x] #2 Both READMEs name v0.39.0
- [x] #3 CI green and Copilot review processed on the release PR
- [x] #4 Tag v0.39.0 points at a verified commit on origin/main and the GitHub release body is not empty
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released v0.39.0. PR #172 merged as ccd6fa1 with CI green; annotated tag v0.39.0 points at that commit (verified through the API and locally with rev-list); GitHub release published with a body of 8659 characters. Copilot review was requested twice and errored both times, so every factual claim in the notes was checked against the code instead and recorded on the PR. Gate: full suite 2039 passed, 4 skipped, 2 failed (test_proc_bounded, Windows-local, green on the CI runner); documentation subset 56 passed. The owner vault was upgraded from the tag: scripts 151 to 133, no retired script left, schema 0.39.0, doctor 181 PASS.
<!-- SECTION:FINAL_SUMMARY:END -->
