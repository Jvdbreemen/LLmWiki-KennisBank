---
id: TASK-85
title: 'Atlas: launch.py laat wees-processen achter op Windows (job object fix)'
status: In Progress
assignee: []
created_date: '2026-07-27 00:09'
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
- [ ] #1 On Windows, killing the launcher process (hard kill, no signal) also terminates the sidecar and vite children
- [ ] #2 POSIX path unchanged (signal handlers still used)
- [ ] #3 Verified live: start launcher, hard-kill it, confirm no orphan atlas.sidecar/vite processes remain
- [ ] #4 pytest suite green
<!-- AC:END -->
