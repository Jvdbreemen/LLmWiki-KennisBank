---
id: TASK-140
title: >-
  Single-flight locks break on Windows: a fresh mtime can read as "in the
  future"
status: Done
assignee: []
created_date: '2026-08-12 15:58'
updated_date: '2026-08-12 17:27'
labels:
  - bug
  - windows
  - reliability
  - tests
dependencies: []
references:
  - scripts/sweep-launch.py
  - scripts/index-launch.py
  - scripts/kb-session-start.py
  - scripts/_embeddings.py
priority: high
ordinal: 134700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Three lock implementations treat a negative age (`time.time() - mtime < 0`) as clock skew and reclaim the lock. On Windows that condition fires on a lock the process just created, so single-flight silently does not hold.

Cause, measured on this machine (5000 create-then-stat samples, Python 3.12, NTFS temp dir):

- `time.get_clock_info('time')` -> `implementation='GetSystemTimeAsFileTime()'`, `resolution=0.015625` (15.625 ms).
- The file's `st_mtime` is recorded from a finer clock than `time.time()` reads, so a just-created file can carry an mtime AHEAD of the next `time.time()` call.
- 586 of 5000 samples (11.7%) had `age < 0`; observed spread `min -0.000000 / median 0.000000 / max 0.016095`.

Affected:

- `scripts/sweep-launch.py:40` — `return age > STALE_SEC or age < 0`. `acquire_lock()` then unlinks a live lock and re-creates it, so two capture sweeps can run at once.
- `scripts/index-launch.py:136` — same expression, same effect: two index builders writing `kb-index.db` concurrently, which is the exact thing TASK-63 put behind one lock.
- `scripts/kb-session-start.py:268` — `if 0 <= age <= LOCK_STALE_SECONDS: return False`; a negative age falls through to unlink + re-create, so the SessionStart coordinator lock is breakable too.
- `scripts/_embeddings.py:352` — `warm_in_progress()` reads a marker written seconds ago as "not running" and a second warm child may be spawned. Harmless in effect, same root cause.

How it surfaced: `tests/test_sweep_launch.py::test_acquire_then_second_fails` failed once in a full local run (`1 failed, 1199 passed`) and passed both in isolation and on a clean worktree run of the same commit (`1200 passed`). CI is Linux, where the clock resolution is nanoseconds, so it never fails there. A ~12% flake in the gate is worse than the bug it hides.

Direction: the `age < 0` clause exists so a lock stamped far in the future does not block maintenance forever. Keep that, but make the window symmetric — `abs(age) > STALE_SEC` — so measurement noise below the clock's own resolution is not mistaken for skew. Both existing future-mtime tests use offsets well past STALE_SEC (+7200 s, +10000 s) and keep their meaning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A test proves acquire_lock() refuses a second acquire when the lock was created microseconds earlier, for sweep-launch.py, index-launch.py and kb-session-start.py
- [x] #2 The existing far-future-mtime tests still pass: a lock stamped beyond STALE_SEC into the future is still reclaimed
- [x] #3 _embeddings.warm_in_progress() reports a marker written just now as running
- [x] #4 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed by making the window symmetric (`abs(age) > STALE_SEC`) in sweep-launch.py, index-launch.py, kb-session-start.acquire_lock and _embeddings.warm_in_progress. A genuine clock change still expires a lock, so both existing far-future tests (+7200 s, +10000 s) keep their meaning unchanged.

tests/test_lock_clock_skew.py stamps the skew explicitly (+0.01 s, below one clock tick) rather than racing the real clock: a live run reproduces the condition about one call in eight, which is no regression guard at all.

Worth recording, because it cost a full debug cycle: the FIRST version of that test popped `_embeddings` from sys.modules and re-imported it. That broke two reconcile tests in test_memory_sweep 400 tests later. Modules imported before the pop (_reconcile, _maintenance) kept the OLD module object, so test_memory_sweep's mock of `emb.embed` landed on the new object while reconcile still called the unmocked one, hit the dead test endpoint, got no vector and fell back to ADD -- `reconciled_superseded` 0 instead of 1. The test now patches `_warm_marker` and restores it in a finally, and touches sys.modules not at all.

Gate: `python -m pytest tests -q` -> 1217 passed, 2 skipped in 5:01, exit 0.

Separate finding, NOT fixed here: tests/__init__.py pins the embed/LLM endpoints to 127.0.0.1:1 on the premise that 'the OS returns RST immediately, so there is no timeout wait'. On this machine every closed loopback port times out instead -- measured 2012 ms to :1, :9 and a freshly released ephemeral port. The local suite pays that wait wherever a code path still attempts a connection, and any timeout-sensitive assertion is a latent flake. Changing the port does not help.

Review follow-up (commit b418e13): the same single-flight hole turned out to exist one level below the mtime. index-launch's _create() opens the lock with O_EXCL and writes the PID as a SECOND step, so a process that loses that race reads an empty file, _lock_pid returns None, _pid_alive(None) is False, and it declares the winner dead and takes the lock. Window is microseconds -- the same order as the clock noise this task measured. Fixed with PID_GRACE_SEC (5 s): an unreadable lock counts as freshly created until it is also old, and only then as orphaned. Two tests cover both halves.

Also from the review, same class: warm_async's own sentinel still used the one-sided comparison, so a marker stamped hours ahead suppressed every prewarm until wall-clock time caught up. Paired with the new session-start notice that reads as 'embedding-model koud' forever about a warm-up that never fires.
<!-- SECTION:NOTES:END -->
