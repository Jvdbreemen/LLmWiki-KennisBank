---
id: TASK-78
title: build-graph-index.py opnemen in index-launch JOBS
status: In Progress
assignee: []
created_date: '2026-07-26 13:46'
labels: []
dependencies: []
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
build-graph-index.py wordt vandaag door geen enkele launcher aangeroepen; kb-graph.db veroudert stil na een graphify-run. Fix: als job opnemen in index-launch.py JOBS zodat de detached worker hem meeneemt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 build-graph-index.py staat in JOBS,bestaande testsuite groen
<!-- AC:END -->
