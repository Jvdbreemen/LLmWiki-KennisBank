---
id: TASK-199
title: Release v0.34.0 - grounded verify stops starving on settled verdicts
status: In Progress
assignee: []
created_date: '2026-08-17 21:06'
labels:
  - release
dependencies: []
priority: high
type: chore
ordinal: 167700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut v0.34.0 from `origin/main` at f205158.

Carries TASK-198: trap 1 recorded nothing about what it had already judged, so a stable `partial` verdict became a permanent claim on `VERIFY_PASS_CAP`. Measured 40 of 40 slots held by known-partial memories while 49 newer ones were never judged at all.

Minor rather than patch, despite every commit carrying `fix:`/`docs:`:
- new CLI flag `kb-verify.py --retry-settled`
- two new environment variables (`KB_VERIFY_RETRY_DAYS`, `KB_VERIFY_RETRY_HOURS`)
- new state file `.claude/memory-verify-attempts.json`
- two new heartbeat keys (`rot_waiting`, `rot_undecided`)
- the session-start memory message changed, which is a changed output contract

Delta v0.33.0..f205158: aacb802, f92879b, 17b1cf9, 496f2b4, 24dd6bc plus the merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CHANGELOG.md carries a dated [0.34.0] section and both compare links are updated
- [ ] #2 README.md and README.nl.md highlight sections are updated in the same edit
- [ ] #3 Full suite green before the docs edit, documentation subset green after
- [ ] #4 PR opened against origin/main, CI green, Copilot review processed
- [ ] #5 Merge verified present on origin/main before tagging
- [ ] #6 Tag v0.34.0 points at the verified origin/main SHA (git rev-list -n1 equals it)
- [ ] #7 GitHub release published with a non-empty body
- [ ] #8 TASK-198 and this task set to Done
<!-- AC:END -->
