---
id: TASK-183
title: Index lock handoff window allows two maintenance workers
status: Done
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

index-launch.py: the launcher writes the lock with its own PID, spawns the
detached worker and exits; until _adopt_lock rewrites the PID (~0.1-1s of
Python startup), the lock names a dead process and is_stale() (line ~157)
returns True immediately — `if not _pid_alive(pid): return True` has no
grace window. acquire_lock's stat/read -> unlink -> create is not atomic
against the worker's os.replace adoption, so a second client's
SessionStart (four clients install hooks) can unlink the just-adopted
live lock and spawn a second worker: two builders writing kb-index.db
concurrently, the double-build TASK-63/140 exist to prevent.

Same family: _pid_alive exists twice with divergent semantics —
index-launch.py:99 treats PermissionError as alive, _embeddings.py:318
catches bare OSError so EPERM reads as dead (duplicate warm spawns), and
the abs(age) skew window is hand-copied at four sites. One shared
lock/proc helper would fix the race once and end the divergence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A dead-PID lock younger than a grace window is not stealable (handoff survives worker startup)
- [ ] #2 Reclaim is atomic against adoption (no unlink of a lock another process just adopted)
- [ ] #3 One shared pid_alive with PermissionError=alive semantics, used by all callers
- [ ] #4 A test drives the launcher->worker handoff with a delayed adopt and asserts single-flight holds
<!-- AC:END -->

## Close-out (2026-08-16)

Fixed on chore/backlog-zero: dead-pid locks respect PID_GRACE_SEC (the launcher->worker handoff is not an orphan), every lock-file mutation runs under an OS-level mutex with a re-judge inside it (the reclaim-vs-adopt race deleted a live lock, reproduced deterministically), and _pid_alive/outside_window live once in _common (the _embeddings copy read PermissionError as dead; explicit ctypes prototypes; never os.kill-probe on Windows).
