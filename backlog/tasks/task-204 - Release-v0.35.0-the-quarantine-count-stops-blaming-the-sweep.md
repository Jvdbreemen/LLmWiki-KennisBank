---
id: TASK-204
title: Release v0.35.0 - the quarantine count stops blaming the sweep
status: In Progress
assignee: []
created_date: '2026-08-18 17:08'
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
- [ ] #1 CHANGELOG.md has a dated [0.35.0] section and both compare links updated
- [ ] #2 README.md and README.nl.md highlight sections both updated to v0.35.0
- [ ] #3 python -m pytest tests -q is green before the documentation edits
- [ ] #4 The documentation test subset is green after the documentation edits
- [ ] #5 Pull request opened against origin/main, CI green, Copilot review processed or its absence reported
- [ ] #6 Tag v0.35.0 placed on a SHA verified to be on origin/main after the merge
- [ ] #7 GitHub release published with a non-empty body
<!-- AC:END -->
