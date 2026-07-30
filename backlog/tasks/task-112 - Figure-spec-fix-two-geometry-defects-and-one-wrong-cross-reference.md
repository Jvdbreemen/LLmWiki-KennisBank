---
id: TASK-112
title: 'Figure spec: fix two geometry defects and one wrong cross-reference'
status: To Do
assignee: []
created_date: '2026-07-30 05:42'
labels:
  - docs
  - c4
  - accuracy
dependencies: []
ordinal: 114700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Narrowly checking every coordinate in the drawing specification against the declared canvas and box geometry surfaces two errors that would make a faithful renderer draw the plate wrong, plus one internal cross-reference that points at the wrong Part.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Connector C5 starts on H1's actual bottom edge. It currently starts at x=1493 while H1 spans x=720 to x=1480 (x + w = 720 + 760), so its origin sits 13 px outside the box it claims to leave. The fix keeps C5 inside the D3/D4 gap (x=1471 to x=1515), so the new origin must satisfy both constraints
- [ ] #2 Caption Z1 respects the 36 px safe margin declared in B1. Its baseline is currently y=1418 on a 1440 px canvas, which leaves 22 px and violates the margin (maximum baseline is y=1404)
- [ ] #3 Part A3 item 6 references the Part that actually contains the metrics. It currently says no numbers other than those given in Part D, but Part D is Connectors; the metrics (2.0 s budget, 20 commands, 4 skills, 8 tools, 1099 tests) live in Parts B and C
- [ ] #4 A full re-check of the remaining coordinates is recorded in the task notes, so the next reader knows the geometry was verified as a whole and not only at the two failing points
<!-- AC:END -->
