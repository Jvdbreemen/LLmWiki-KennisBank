---
id: TASK-241
title: Use bounded canonical projection health in the setup doctor
status: Done
assignee: []
created_date: '2026-09-08 05:41'
updated_date: '2026-09-09 06:12'
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
- [x] #4 Focused shell and doctor tests plus the full suite pass; sanitized evidence records the former failure and the limits
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Exercise the existing 13e doctor section through Git Bash with temporary vaults and a deterministic CLI stub. 2. Record failing assertions before changes. 3. Add a content-free shell summary mode to the canonical projection doctor and replace the stale shell logic with that one bounded call. 4. Verify disabled/enabled states, schema failures, forbidden flags, unknown checks, subprocess failure, and full-suite integration. 5. Keep owner canary and release gates unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Red before implementation: 4 failed, 1 passed in 2.54s, including the actual Bash entrypoint section missing --fast/--shell-summary. Canonical CLI now renders content-free source, ledger and projection rows; setup removes retired flag/schema checks and calls bounded summary mode. Focused doctor/observability/discovery run: 15 passed in 4.48s; Git Bash syntax validation passes. Real fast owner-vault summary completed read-only: 16286 source documents present but integrity/inventory not checked; ledger 42 events/42 outcomes/1 review; projection 1 record; both explicit read routes disabled. Full-suite AC4 remains open.

Final focused set after cleanup review: 34 passed in 5.26s; independent unittest discovery retained all 17 measurement tests (0.423s). Shell mode is forced fast even alongside --deep. Source presence is not promoted to PASS, unavailable checks remain explicit, and raw reasons are never rendered.

Clean cf3062787a446908898055744ae4fc5302a3fb7b full repository run: 2026 passed, 4 existing skips, zero errors/failures in 604.39s. The complete suite includes shell doctor and cross-client setup smokes. Atlas typecheck and 39/39 frontend tests separately passed. Live deployment remains a separate operational gate.

Live supported setup exposed four false missing-command warnings: doctor checks the new source/experience commands at the root, although setup correctly installed the documented kennisbank/ namespace. Reopening the final integration gate for an entrypoint regression test and scoped path fix. Canonical bounded projection health itself passed. Overall live doctor also fails on six pre-existing wiki provenance problems; those claims will not be invented or waived.

Clean-start runtime b74a008 full suite completed: 2032 passed, 4 existing skips, zero failures/errors in 825.12 seconds; JUnit 2036 tests, 825.094 seconds, SHA256 374cc3eef18b0146bead9aed14fdbf26097c11a0714f5c32b034679e27c20459. Only documentation/backlog changed during execution; scripts/tests remain identical. Supported live setup recheck stays under TASK-236.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Supported setup now uses the canonical bounded projection doctor and reports explicit routes, append-only ledger and derived projection separately. Unknown source checks remain unknown; private diagnostic text is not rendered. Actual Git Bash red/green entrypoint tests and clean full-suite evidence are recorded.
<!-- SECTION:FINAL_SUMMARY:END -->

2026-09-09: Namespace follow-up implemented test-first. Real Bash regression:
1 failed / 7 passed before repair; 8 passed after repair. Combined projection,
migration and Copilot doctor tests: 19 passed in 97.95s. Root-level decoys cannot
satisfy missing namespaced commands. Full-suite and live setup recheck remain
open; evidence appended to setup-projection-health-evidence-2026-09-08.md.
