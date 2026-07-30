---
id: TASK-112
title: 'Figure spec: fix two geometry defects and one wrong cross-reference'
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 05:42'
updated_date: '2026-07-30 17:54'
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
- [x] #1 Connector C5 starts on H1's actual bottom edge. It currently starts at x=1493 while H1 spans x=720 to x=1480 (x + w = 720 + 760), so its origin sits 13 px outside the box it claims to leave. The fix keeps C5 inside the D3/D4 gap (x=1471 to x=1515), so the new origin must satisfy both constraints
- [x] #2 Caption Z1 respects the 36 px safe margin declared in B1. Its baseline is currently y=1418 on a 1440 px canvas, which leaves 22 px and violates the margin (maximum baseline is y=1404)
- [x] #3 Part A3 item 6 references the Part that actually contains the metrics. It currently says no numbers other than those given in Part D, but Part D is Connectors; the metrics (2.0 s budget, 20 commands, 4 skills, 8 tools, 1099 tests) live in Parts B and C
- [x] #4 A full re-check of the remaining coordinates is recorded in the task notes, so the next reader knows the geometry was verified as a whole and not only at the two failing points
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Full coordinate re-check, not only the two failing points.

C5 was the only connector whose origin fell outside the box it named. H1 spans x=720 to x=1480 (x + w = 720 + 760) and C5 started at x=1493, 13 px past the edge. The replacement x=1476 is the only kind of value that satisfies both constraints at once: it is on H1's bottom edge, and it is inside the D3/D4 vertical gap (D3 right edge 1471, D4 left edge 1515) that Part D2 requires C5 to pass through. The usable overlap is just x=1471 to x=1480, so 1476 sits mid-window with 5 px clearance from D3. The label chip moved with it, 1535 to 1518, keeping its original 42 px offset.

Everything else checks out. Verified: H1 720-1480 against C1 at 860, C2 at 1340, C3 leaving the right edge at exactly 1480, C4 at 1032 inside the D2/D3 gap (1010 to 1054), C10 at 1150 and C11 at 1440 both within H1's span. D-boxes at 132/593/1054/1515 with width 417 give right edges 549/1010/1471/1932, matching C8, C9 and C13. S2 x=1252 w=680 gives right edge 1932, matching C12. E1 spans 60 to 2500 and 306 to 1214 on a 2560 x 1440 canvas, leaving the 36 px margin intact at 2524 and putting M1 at y=1252 correctly outside. E2's tab centre (848 + 432 = 1280) matches E1's centre (60 + 1220 = 1280). R1, R2 and R3 at x=2036 w=400 end at 2436, inside the boundary.

Only the caption broke the margin: baseline y=1418 on a 1440 canvas leaves 22 px where B1 declares 36, so the maximum is y=1404. Moved there, which still leaves 22 px below the legend baseline at 1382.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixes two geometry errors and one wrong internal cross-reference in the architecture-overview drawing specification. All three would survive a casual read and only surface when a renderer takes the coordinates literally.

Connector C5 claimed to leave H1's bottom edge at x=1493, but H1 spans x=720 to x=1480, so its origin sat 13 px outside the box. Moved to x=1476, which is the narrow window (1471 to 1480) that is simultaneously on H1's edge and inside the D3/D4 gap the spec requires C5 to pass through. The label chip moved with it.

Caption Z1 sat at baseline y=1418 on a 1440 px canvas, breaking the 36 px safe margin the spec declares for itself in B1. Moved to y=1404.

Part A3 told the renderer to invent no numbers beyond those in Part D, but Part D is Connectors; the metrics live in Parts B and C. Corrected.

A full re-check of every remaining coordinate is recorded in the implementation notes: C5 and Z1 were the only two failures.

Tests: tests/test_docs_consistency.py, 5 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
