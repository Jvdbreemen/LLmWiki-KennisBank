---
id: TASK-216
title: Persist injection attribution and measure weak session outcomes
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - outcome-telemetry
  - usage
  - attribution
  - measurement
dependencies:
  - TASK-173
  - TASK-179
  - TASK-212
ordinal: 175500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the measurement-only outcome loop. Persist which wiki, memory,
experience, and source items were exposed in which session and task/work-unit,
then join them to weak outcome evidence collected from local artefacts.

The initial outcome record is evidence-shaped, not a single reward score. It
may contain tests passed/failed, a relevant commit or diff, a revert or follow-up
failure, explicit user feedback where available, contradiction or supersession,
and an `unknown` state. Session-level observations must not be presented as
causal proof that an individual memory helped.

Resolve the sensor gap in TASK-179 before using usage data downstream. Verify
all supported clients and transcript formats. Keep this work off the hot path;
session-end or idle processing is acceptable, but failure must not block a
session.

This task must not change retrieval ranking, noise marking, memory promotion,
or skill promotion. It produces the ledger and the first correlation report
only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A persistent ledger links every exposed item to session, task/work-unit, query, layer, rank, timestamp, and source/provenance id
- [ ] #2 Labelled per-client usage tests from TASK-179 pass or record a measured limitation for in-context use
- [ ] #3 A weak outcome record is derived from existing local artefacts and preserves success, failure, mixed, and unknown evidence states
- [ ] #4 The ledger distinguishes exposure, read/use evidence, outcome evidence, and attribution strength
- [ ] #5 A correlation report compares exposed items in outcome groups without claiming individual causality
- [ ] #6 No recall-time latency, ranking, memory status, noise status, or skill state changes
- [ ] #7 Missing transcripts, mixed-task sessions, failed tests, unrelated commits, and session-end crashes are tested
- [ ] #8 The report states what additional signal would be required before outcome-aware ranking could be justified
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
This is the implementation of the measurement scope already described by
TASK-173. Do not close TASK-173 by merely adding a scalar session score; retain
the evidence ledger and attribution limitations.
<!-- SECTION:NOTES:END -->

