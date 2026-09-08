---
id: TASK-241
title: Use bounded canonical projection health in the setup doctor
status: In Progress
assignee: []
created_date: '2026-09-08 05:41'
updated_date: '2026-09-08 05:54'
labels:
  - bug
  - production
  - observability
dependencies: []
references:
  - docs/research/setup-projection-health-evidence-2026-09-08.md
ordinal: 180600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The supported setup doctor still reads retired recall flags and the mixed experience schema, then runs the unbounded deep source inventory. Connect it to the canonical split-store fast health report without claiming skipped checks passed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tests first reproduce incorrect routes, split-store reporting and the missing bounded mode at the actual shell entrypoint
- [x] #2 The setup doctor uses the explicit source and experience routes and separately reports canonical ledger and derived projection
- [x] #3 Routine setup uses --fast, reports unknown checks as not checked, and warns on forbidden flags or unhealthy stores without printing private content
- [ ] #4 Focused shell and doctor tests plus the full suite pass; sanitized evidence records the former failure and the limits
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Exercise the existing 13e doctor section through Git Bash with temporary vaults and a deterministic CLI stub. 2. Record failing assertions before changes. 3. Add a content-free shell summary mode to the canonical projection doctor and replace the stale shell logic with that one bounded call. 4. Verify disabled/enabled states, schema failures, forbidden flags, unknown checks, subprocess failure, and full-suite integration. 5. Keep owner canary and release gates unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Red before implementation: 4 failed, 1 passed in 2.54s, including the actual Bash entrypoint section missing --fast/--shell-summary. Canonical CLI now renders content-free source, ledger and projection rows; setup removes retired flag/schema checks and calls bounded summary mode. Focused doctor/observability/discovery run: 15 passed in 4.48s; Git Bash syntax validation passes. Real fast owner-vault summary completed read-only: 16286 source documents present but integrity/inventory not checked; ledger 42 events/42 outcomes/1 review; projection 1 record; both explicit read routes disabled. Full-suite AC4 remains open.

Final focused set after cleanup review: 34 passed in 5.26s; independent unittest discovery retained all 17 measurement tests (0.423s). Shell mode is forced fast even alongside --deep. Source presence is not promoted to PASS, unavailable checks remain explicit, and raw reasons are never rendered.
<!-- SECTION:NOTES:END -->
