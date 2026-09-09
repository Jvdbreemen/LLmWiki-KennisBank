---
id: TASK-247
title: >-
  A hard kill leaves the sweep lock behind, and the next sweep skips itself for
  up to an hour
status: Done
assignee: []
created_date: '2026-09-09 18:36'
updated_date: '2026-09-09 23:09'
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
- [x] #1 An orphaned lock whose named PID does not exist is released on the next acquire attempt, without waiting out STALE_SEC
- [x] #2 A lock whose PID does exist keeps its current time-based treatment, so PID reuse cannot free a live lock
- [x] #3 A test covers both directions: a dead PID releases, a live PID does not
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add a PID probe ALONGSIDE the time lease, never in place of it.

1. The token gains a host: host:pid:random instead of pid:random. Without it the probe judges a PID number that may belong to another machine on a shared vault, and 'that number is free here' would steal a live lock.
2. _owner(token) returns (host, pid), or None for the old two-part format and anything that does not parse. No owner known means no PID judgement, which is exactly the pre-fix behaviour.
3. _pid_alive(pid) returns True, False, or None for 'cannot tell'. On POSIX os.kill(pid, 0). NOT on Windows: CPython translates every signal other than CTRL_C_EVENT and CTRL_BREAK_EVENT into TerminateProcess, so the usual probe would kill the process it is meant to ask about. Windows goes through OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION plus GetExitCodeProcess.
4. is_orphaned(lock) is True only when the token names THIS host and a PID that is definitively gone. Every uncertainty falls to False, so uncertainty means respecting the lock.
5. is_free(lock) = is_stale(lock) or is_orphaned(lock). Used by acquire_lock and by sweep-launch._lock_alive, which is where the visible symptom lived: the launcher refused to spawn with 'er draait al een sweep'.

Out of scope: memory-notify._worker_running reads the INDEX lock from index-launch.py, a different lock with its own token format.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as planned, plus one thing the plan did not foresee.

Reclaiming a lock now re-reads the token and removes only the one it just judged. Two acquirers that see the same orphan would otherwise both clear it and both take it, the second discarding the first's fresh lock. That race predates this change: acquire_lock has always done judge-then-unlink. What changes is reachability. An orphan used to surface only after STALE_SEC, so two processes were never realistically inside that window together; a probe that answers immediately puts them there. Widening the door is my change, so closing it belongs to this task.

Ten tests in tests/test_sweepstate.py::VerweesdeLockTest. Falsified against the pre-fix implementation: nine fail, and the two that carry the claim fail on behaviour rather than on a missing attribute (acquire_lock returns None for a dead holder; sweep-launch._lock_alive reports a dead holder as a running sweep). The race test was falsified separately by removing only the two guard lines: without them the acquirer takes over the winner's fresh lock.

One test ordering detail worth recording. The core test first asserted is_orphaned and then acquire_lock. Both orderings are wrong for different reasons: is_orphaned first makes the test fail on AttributeError against the old code rather than on the defect, and is_orphaned after acquire_lock inspects a file whose token acquire_lock has already replaced with this live process. Split into a behavioural test and a unit test.

Not covered: what kills the worker in the first place. On 2026-09-09 the sweep's own wrapper was killed for low memory while the python child kept running, which is a separate matter from the lock.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed in commit 316d79a and installed into the Kluis vault. Smoke-tested against the real vault in both directions: a fresh lock naming a dead PID reads is_stale False, is_orphaned True, is_free True and sweep-launch._lock_alive False; the same lock naming this live process reads is_orphaned False and _lock_alive True. The smoke lock was removed again.

Ten tests in tests/test_sweepstate.py::VerweesdeLockTest; nine fail against the pre-fix implementation and the two carrying the claim fail on behaviour, not on a missing attribute.

One addition beyond the plan: acquire_lock re-reads the token and removes only the lock it just judged. That race predates the change but was unreachable while an orphan took an hour to surface; an immediate probe puts two acquirers inside the window. Falsified separately by removing only the guard's two lines.
<!-- SECTION:FINAL_SUMMARY:END -->
