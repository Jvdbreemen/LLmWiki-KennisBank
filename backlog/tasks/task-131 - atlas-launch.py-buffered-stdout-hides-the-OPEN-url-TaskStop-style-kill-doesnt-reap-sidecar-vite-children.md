---
id: TASK-131
title: >-
  atlas/launch.py: buffered stdout hides the OPEN url; TaskStop-style kill
  doesn't reap sidecar/vite children
status: To Do
assignee: []
created_date: '2026-08-03 21:56'
updated_date: '2026-08-03 22:42'
labels:
  - atlas
  - dev-experience
  - windows
dependencies: []
modified_files:
  - atlas/launch.py
priority: low
ordinal: 126700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two small dev-workflow rough edges found while measuring TASK-91 AC#8 (2026-08-03):

1. launch.py's own print()s ("[atlas] sidecar -> ...", "[atlas] vite -> ...", "[atlas] OPEN: ...") never showed up in a log file the process's stdout was redirected into, even ~70s after startup, while the sidecar's and vite's own child-process output appeared immediately. Python block-buffers stdout when it is not a TTY and launch.py never flushes; any log-tailing tooling (or a human watching a redirected log instead of an interactive terminal) never sees the URL. Fix: `print(..., flush=True)` on the three launcher prints, or run Python with `-u`.

2. Terminating the launch.py process via an external stop (observed via a session-management TaskStop call, not Ctrl-C/SIGINT) left the sidecar and vite child processes running and bound to their ports; had to be force-killed manually by PID via Get-NetTCPConnection. launch.py's own `_windows_kill_on_close_job()` docstring says this exact scenario (a terminated launcher whose SIGTERM handler never runs) is precisely what the Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE is for -- but it did not fire. Reproduced twice in the same session. Needs investigation into whether the external stop mechanism actually terminates the process (vs. detaching/closing a pipe) and whether the job handle is really being held for the process's full lifetime.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 launcher prints flush immediately (visible in a redirected/piped log within ~1s of being printed)
- [ ] #2 Reproduce the orphaned-children case under a real Ctrl-C and confirm the Job Object DOES clean up there (isolates whether the bug is Job-Object-specific or stop-mechanism-specific)
- [ ] #3 Investigate why the external-stop path leaves children alive; either fix or document as a known limitation with a manual-cleanup note in atlas/README.md
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-03 22:42
---
2026-08-03: AC#1 done -- flush=True added to the three launcher print()s. Verified by relaunching and tailing the redirected log: the sidecar/vite lines now appear within ~2s (previously absent even after 70s+), and OPEN appears once the health probe succeeds. AC#2/#3 (the Job Object not reaping children on an external stop) deliberately left open -- reproduced a third time this session (ports 33875/33876 stayed bound after TaskStop, force-killed by PID again) but investigating why the Job Object doesn't fire is a real Windows-specific dig that does not belong bundled into this session's sweep. Left as To Do for that specific remaining piece.
---
<!-- COMMENTS:END -->
