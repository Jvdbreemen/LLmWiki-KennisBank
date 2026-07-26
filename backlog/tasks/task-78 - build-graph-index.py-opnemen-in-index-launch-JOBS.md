---
id: TASK-78
title: build-graph-index.py opnemen in index-launch JOBS
status: Done
assignee: []
created_date: '2026-07-26 13:46'
updated_date: '2026-07-26 18:25'
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
- [x] #1 build-graph-index.py staat in JOBS,bestaande testsuite groen
<!-- AC:END -->



## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in v0.22.0: commit e92ae03 (PR #73, merged 62242a6) adds build-graph-index.py to the index-launch worker JOBS. Verified present in scripts/index-launch.py on origin/main and covered by the v0.22.0 changelog entry. Status was left In Progress by oversight; closed against this evidence.
<!-- SECTION:FINAL_SUMMARY:END -->
