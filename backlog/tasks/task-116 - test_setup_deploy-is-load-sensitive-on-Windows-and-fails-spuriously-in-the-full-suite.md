---
id: TASK-116
title: >-
  test_setup_deploy is load-sensitive on Windows and fails spuriously in the
  full suite
status: To Do
assignee: []
created_date: '2026-07-30 05:49'
labels: []
dependencies: []
ordinal: 114700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured twice on 2026-07-29/30: tests/test_setup_deploy.py produces 4-5 failures (including test_hook_registration_preserves_existing_settings and test_rerun_preserves_user_data_and_refreshes_tooling) during a full local suite run on Windows, while the same file passes 22/22 in isolation (463s) and the whole suite passes on the Linux CI runner. Both failing runs happened while the machine was saturated: two 30-agent workflows with 1500+ tool calls plus an eval over 1550 questions. The file shells out to the real setup.sh, so it spawns bash and python subprocesses and is timing-sensitive in a way the rest of the suite is not. This makes the local gate untrustworthy exactly when a developer is busiest, which is the worst possible moment for a false red. Investigate whether the tests carry an implicit timeout, whether they can be made load-independent (explicit waits rather than fixed sleeps, or a slower budget on Windows), and whether the suite should mark them so a false red is distinguishable from a regression. Do not simply raise a timeout without establishing what actually times out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Root cause established: what exactly fails under load (which subprocess, which wait, which assertion)
- [ ] #2 Fix makes the tests pass in a saturated full-suite run on Windows, or they are explicitly marked and reported as load-sensitive rather than failing silently
- [ ] #3 No timeout is raised without evidence of what it is waiting for
- [ ] #4 Full suite green locally on Windows under load
<!-- AC:END -->
