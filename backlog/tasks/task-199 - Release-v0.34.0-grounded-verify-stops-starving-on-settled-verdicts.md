---
id: TASK-199
title: Release v0.34.0 - grounded verify stops starving on settled verdicts
status: Done
assignee: []
created_date: '2026-08-17 21:06'
updated_date: '2026-08-17 21:49'
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
- [x] #1 CHANGELOG.md carries a dated [0.34.0] section and both compare links are updated
- [x] #2 README.md and README.nl.md highlight sections are updated in the same edit
- [x] #3 Full suite green before the docs edit, documentation subset green after
- [x] #4 PR opened against origin/main, CI green, Copilot review processed
- [x] #5 Merge verified present on origin/main before tagging
- [x] #6 Tag v0.34.0 points at the verified origin/main SHA (git rev-list -n1 equals it)
- [x] #7 GitHub release published with a non-empty body
- [x] #8 TASK-198 and this task set to Done
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
v0.34.0 released.

- Tag `v0.34.0` -> `110d57e`, verified with `git rev-list -n1` equal to the merged `origin/main` SHA before publishing, so the tag points at code main actually contains.
- GitHub release published, body 4991 characters (checked non-empty; a previous release shipped an empty one).
- Gate: full suite 1598 passed / 3 skipped on the released code, documentation subset 56 passed after the changelog and README edits.
- PR #140 against origin/main, CI green (`atlas`, `test`).

Copilot did not review #140. It also did not review #139 (the code) or #137 (the previous release), so this is the upstream repository or a quota, not this PR. Two things bounded the risk and the owner decided to proceed on that basis: the code itself was Copilot-reviewed on fork PR rvdbreemen/LLmWiki-KennisBank#5 (5 comments, all verified and applied) and merged unchanged as #139, and the #140 diff is four `.md` files with no code, verified against `origin/main`.

Version choice was minor rather than patch even though every commit carried `fix:`/`docs:`: new CLI flag `--retry-settled`, two new environment variables, a new state file, two new heartbeat keys, and a changed session-start output contract.
<!-- SECTION:FINAL_SUMMARY:END -->
