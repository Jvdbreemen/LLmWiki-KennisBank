---
id: TASK-95
title: 'Fix console popups: index-launch worker jobs need CREATE_NO_WINDOW'
status: Done
assignee: []
created_date: '2026-07-29 18:28'
updated_date: '2026-07-29 18:44'
labels: []
dependencies: []
ordinal: 98700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On Windows, index-launch.py's detached worker (DETACHED_PROCESS|CREATE_NO_WINDOW) runs each maintenance job via subprocess.run without creationflags. A console-less parent spawning a console-subsystem child (python.exe) makes Windows allocate a new visible console per job, so users see multiple popup CLI windows at every Claude session start.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 run_jobs default runner passes CREATE_NO_WINDOW on os.name == 'nt'
- [ ] #2 pytest suite green
- [ ] #3 deployed Kluis copy updated
<!-- AC:END -->
