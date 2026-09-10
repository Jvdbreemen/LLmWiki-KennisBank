---
id: TASK-245
title: Address automated experience evaluation release gaps
status: In Progress
assignee: []
created_date: '2026-09-09 17:41'
labels:
  - evaluation
  - experience
  - pilot
dependencies:
  - TASK-244
ordinal: 184600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Resolve the specific gaps measured by the completed autonomous evaluation in
TASK-244. This item replaces an accidentally duplicated evaluation task; it
does not represent a second successful evaluation.

Evidence: `docs/research/automated-experience-regression-evidence-2026-09-09.md`.
No additional owner case-label batch is required for the engineering work.
Keep production read flags unchanged until the resulting acceptance evidence
and deployment prerequisites support activation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Define and test mixed wiki/raw provenance handling before implementation; trace supporting raw evidence without broadening approved roots or silently discarding required evidence, and retain unresolved fixtures in the full denominator
- [ ] #2 Add applicability/abstention failure tests before implementation; calibrate only on a separate development set and freeze new evaluation inputs before testing, targeting >=90% negative no-hit specificity without sacrificing the >=85% positive hit@3 criterion. **Tests and calibration are complete, but no tested arm meets both gates; no production policy is selected.**
- [ ] #3 Measure and address gateway p95 <=250 ms under both ordinary and concurrent maintenance load; measure actual query embedding plus gateway latency separately and preserve initial failed runs. **Gateway and embedding measurements are complete; ordinary end-to-end p95 is 249.6 ms, concurrent p95 is 282.2 ms.**
- [x] #4 Repeat source freshness, exact reconstruction, candidate filtering and prohibited-mode checks; no production memory/review promotion or telemetry contamination from evaluation
- [x] #5 Publish content-safe before/after evidence, input/runtime hashes and limitations; do not substitute fixture eligibility or model judgments for canonical review or observed natural-use outcomes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the 13 mixed-provenance exclusions and explain which raw evidence
   actually supports each bounded lesson. Preserve original labels and refs.
2. In a separate workstream, create an independent applicability development
   set from source-grounded examples. Test common-word-only and related-but-
   unsupported matches; do not select thresholds on the spent ten negatives.
3. Profile database/extension opening, vector retrieval and concurrent resource
   use separately; do not attribute the initial latency failure to a cause
   without measurements.
4. Freeze regression and new evaluation expectations, implement only justified
   fixes, then run the complete evidence packet autonomously. Keep historical
   A/B utility separate from new ranking and source-integrity results.
<!-- SECTION:PLAN:END -->

## Current evidence

The content-safe aggregate report is
`docs/research/task245-evaluation-evidence-2026-09-10.md`. It records the
private artifact hashes and limitations without copying queries, lesson text,
raw passages, or source paths into the repository. The development split is
sealed from the holdout. Since no applicability policy cleared both gates and
concurrent real embedding plus gateway latency exceeded the target, production
read flags remain unchanged and no third automatic memory route is wired.
