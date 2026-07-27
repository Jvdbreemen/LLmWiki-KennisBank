---
id: TASK-85
title: 'Atlas: launch.py laat wees-processen achter op Windows (job object fix)'
status: Done
assignee: []
created_date: '2026-07-27 00:09'
updated_date: '2026-07-27 00:25'
labels:
  - atlas
  - bug
  - windows
dependencies: []
ordinal: 95000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
launch.py installs SIGINT/SIGTERM handlers, but on Windows a terminated launcher (e.g. the Claude Code background-task wrapper being stopped) never delivers SIGTERM: the handler is dead code and the sidecar + vite children survive as orphans. Observed live: three complete Atlas stacks (3x sidecar + vite) running simultaneously after two wrapper kills and one explicit TaskStop. Fix: on Windows, create a Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE and assign the launcher to it before spawning children; when the launcher dies for any reason the OS tears down the whole tree. POSIX behaviour unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On Windows, killing the launcher process (hard kill, no signal) also terminates the sidecar and vite children
- [x] #2 POSIX path unchanged (signal handlers still used)
- [x] #3 Verified live: start launcher, hard-kill it, confirm no orphan atlas.sidecar/vite processes remain
- [x] #4 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
launch.py now binds itself to a Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE before spawning the sidecar and vite; the OS kills the whole tree when the launcher dies, however it dies. Root cause of the orphans: Python signal handlers never run on Windows process termination. Extra pitfall fixed: ctypes needs explicit HANDLE prototypes or AssignProcessToJobObject fails with ERROR_INVALID_HANDLE. Verified live (hard-kill → 0 orphans); gate 1016 passed, 2 skipped. Merged via PR #81 (c0e42a0). Copilot review unavailable (quota); merged with green gate under standing user instruction.
<!-- SECTION:FINAL_SUMMARY:END -->
