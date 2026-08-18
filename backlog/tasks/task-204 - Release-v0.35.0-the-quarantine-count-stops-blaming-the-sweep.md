---
id: TASK-204
title: Release v0.35.0 - the quarantine count stops blaming the sweep
status: Done
assignee: []
created_date: '2026-08-18 17:08'
updated_date: '2026-08-18 18:07'
labels:
  - release
dependencies: []
type: chore
ordinal: 169700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Release v0.35.0 from main (01a3f68).

Carries:
- TASK-200: doctor.sh reported one quarantine number with two meanings and blamed the sweep for all of it. memory-doctor.py gains `rot --json`; doctor.sh reports waiting and undecided separately, each with advice that applies.
- The C4 architecture documentation set under docs/C4-Documentation (four levels, 28 files, plus OpenAPI for the Atlas sidecar and a tool contract for the 8 MCP tools).
- The Eaves multi-agent memory review and its three follow-up tasks (TASK-201, 202, 203), including the ID renumbering that resolved a collision with upstream.

Version note: the delta contains only fix: and docs: commits, so semver would call this a patch. The owner chose minor deliberately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CHANGELOG.md has a dated [0.35.0] section and both compare links updated
- [x] #2 README.md and README.nl.md highlight sections both updated to v0.35.0
- [x] #3 python -m pytest tests -q is green before the documentation edits
- [x] #4 The documentation test subset is green after the documentation edits
- [x] #5 Pull request opened against origin/main, CI green, Copilot review processed or its absence reported
- [x] #6 Tag v0.35.0 placed on a SHA verified to be on origin/main after the merge
- [x] #7 GitHub release published with a non-empty body
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released v0.35.0. Gate: 1634 passed, 3 skipped (full), 56 passed (doc subset). PR #144 merged by the owner at 2026-08-18T18:03Z; Copilot review did not arrive despite an API request (no workflow run started — absence reported per AC#5). Tag v0.35.0 placed on 1027fcd after verifying origin/main contains the release commit; GitHub release published with a 3170-char body verified non-empty.
<!-- SECTION:FINAL_SUMMARY:END -->
