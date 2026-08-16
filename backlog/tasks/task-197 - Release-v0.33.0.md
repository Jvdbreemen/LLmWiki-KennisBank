---
id: TASK-197
title: Release v0.33.0
status: In Progress
assignee: []
created_date: '2026-08-17 00:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cut v0.33.0 from origin/main 47584cb: the autonomous memory review
(TASK-195, traps 1-3 + audit view), the silent-failure cluster
(TASK-167/180/181/182/185/196), the backlog-zero fix wave
(TASK-158/175/183/184/186/187/188/189/190/191/192), and the backlog
triage to zero. 68 commits since v0.32.0; multiple feat: -> minor.
Procedure per the kennisbank-release skill; tag only a verified
origin/main SHA with ^{}.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CHANGELOG section + compare links, README highlights in both languages
- [ ] #2 Doc-subset tests green after the doc edits
- [ ] #3 PR merged, merge verified on origin/main, tag on the peeled SHA
- [ ] #4 Release published with non-empty body
<!-- AC:END -->
