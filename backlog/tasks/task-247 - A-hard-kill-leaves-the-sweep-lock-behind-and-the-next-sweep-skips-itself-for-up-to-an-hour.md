---
id: TASK-247
title: >-
  A hard kill leaves the sweep lock behind, and the next sweep skips itself for
  up to an hour
status: To Do
assignee: []
created_date: '2026-09-09 18:36'
labels: []
dependencies: []
priority: medium
type: bug
ordinal: 186600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
sweep_lock() releases through a context manager, so an exception or a SIGINT frees it. A hard kill does not run __exit__, and then only the time-based lease frees the file: STALE_SEC is 3600 seconds.

Observed twice in two days in the Kluis vault. On 2026-09-08 a lock naming PID 17192 blocked a sweep with 'er draait al een sweep' while that PID did not exist. On 2026-09-09 at 20:33 a lock written at 19:51 named PID 30968, which also did not exist; the file had not been refreshed since it was written, while a live owner refreshes every LEASE_REFRESH_SEC (30 s). Both were removed by hand to get a sweep going at all.

The lease is time-based on purpose: a PID can be reused, so 'this PID exists' does not prove the owner is the sweep. The reverse does hold with no such caveat. If the named PID does NOT exist, the owner is definitively dead and the lock can go immediately, no reuse question involved. Combining the two keeps the current safety and removes the hour of skipped sweeps.

Second signal, cheaper still: an unrefreshed mtime. A live owner touches the lease every 30 seconds, so a file older than a few refresh intervals is orphaned regardless of what the PID says.

Not investigated: what kills the worker. On 2026-09-09 the lock timestamp (19:51) sits next to a context-compaction event at 19:50, and an earlier run was killed for low memory. Whether the worker dies with the session that launched it is a separate question, and the more interesting one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An orphaned lock whose named PID does not exist is released on the next acquire attempt, without waiting out STALE_SEC
- [ ] #2 A lock whose PID does exist keeps its current time-based treatment, so PID reuse cannot free a live lock
- [ ] #3 A test covers both directions: a dead PID releases, a live PID does not
<!-- AC:END -->
