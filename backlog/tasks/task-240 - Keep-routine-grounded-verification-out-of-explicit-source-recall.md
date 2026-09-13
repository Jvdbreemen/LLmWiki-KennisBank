---
id: TASK-240
title: Keep routine grounded verification out of explicit source recall
status: Done
assignee:
  - '@codex'
created_date: '2026-09-08 05:18'
updated_date: '2026-09-08 17:11'
labels:
  - source-recall
  - production
  - safety
dependencies: []
priority: high
type: bug
ordinal: 179600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Routine grounded verification silently selects source_recall_passage when no callback is supplied. Enabling the explicit source read flag therefore also grants automatic source fallback during memory verification, contrary to the narrowed v1 contract. Require deliberate callback selection for this internal helper and keep routine verification on supplied transcript evidence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A test first reproduces automatic source callback invocation from ordinary verify_grounded without explicit selection
- [x] #2 Default routine verification never invokes source search, regardless of explicit source-read settings
- [x] #3 A caller that deliberately supplies a source verification callback retains the labelled source-recall behavior
- [x] #4 Focused grounded/source/policy tests and current full-suite evidence pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a negative default-call test and observe red. 2. Remove implicit callback selection while retaining explicit dependency injection. 3. Run grounded/source/policy regressions and include in the full suite. 4. Record the corrected scope in evidence.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Red: two new tests failed in 1.07s while the explicit callback positive control passed: default source helper invoked once and routine pass promoted one memory using unrelated source text. Removed implicit default callback selection; explicit callback remains supported. Grounded/source/policy/measurement focused tests: 59 passed in 4.19s. Full-suite proof pending.

Clean cf3062787a446908898055744ae4fc5302a3fb7b full repository run: 2026 passed, 4 existing skips, zero errors/failures in 604.39s. Scoped review confirms no implicit callback selection and unchanged explicit callback control. No owner-vault memories were promoted by this fix.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Routine grounded verification no longer implicitly searches raw sources when the supplied transcript is empty. Explicitly supplied callback behavior is preserved. Red/green isolation tests and full-suite proof establish the intended explicit-only boundary.
<!-- SECTION:FINAL_SUMMARY:END -->
