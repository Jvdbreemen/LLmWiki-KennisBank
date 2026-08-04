---
id: TASK-123
title: Refresh the CI baseline arithmetic in c4-code-github-workflows.md
status: Done
assignee: []
created_date: '2026-07-30 19:12'
updated_date: '2026-08-03 21:27'
labels:
  - docs
  - c4
  - accuracy
dependencies: []
ordinal: 118700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The workflows code-level document quotes 1099 collected tests in five places and builds an analysis on it: it flags the ci.yml comment's own baseline (781 tests in about 20 minutes) as roughly 41 percent behind. The suite now collects 1112, so the document's headline finding is correct in direction but its arithmetic is stale in the same way as the comment it criticises. Deliberately left out of the v0.26.1 documentation-accuracy patch, because updating the numbers means re-deriving the analysis rather than substituting a figure.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All five occurrences of 1099 reflect a freshly measured collect-only count, with the measurement command and its result recorded
- [x] #2 The growth percentage against the ci.yml baseline of 781 is recomputed from the new figure
- [x] #3 The document says how it expects to age, so the next reader knows whether a mismatch is a defect or expected drift
- [x] #4 Consider whether ci.yml:10-16 should carry the corrected baseline, since that comment is the artefact the finding is actually about
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Re-measured with `python -m pytest tests --collect-only -q` on 2026-08-03: 1131 tests (was 1099), 103 test modules (was 101). Growth against the ci.yml comment's 781-test baseline: 45% (was 41% four days ago) -- computed as (1131-781)/781.

All six occurrences of 1099 in c4-code-github-workflows.md updated (lines 149, 167, 171, 264/266, 347/349, 378/380), with the two remaining "1099" mentions left intact on purpose: they narrate the delta from the previous measurement ("was 1099") rather than claiming a current count (AC#1).

The growth percentage recomputed from the fresh figure: 45%, up from 41% (AC#2).

Added an aging note explaining that this is a snapshot that will drift again -- the doc says explicitly to re-derive with the same collect-only command before relying on the percentage for a decision, and that a stable or shrinking gap on a future read is expected drift, not a defect (AC#3).

AC#4, considered rather than blindly applied: did NOT overwrite ci.yml's 781-test baseline, because that comment documents the historical measurement that justified the 30-minute timeout -- replacing it with 1131 would introduce a new false claim ("1131 tests in ~20 min"), never actually measured, in place of an honest historical one. Instead added a short comment in ci.yml pointing to this doc's §4 for the current count and growth analysis, so a reader does not mistake 781 for a live figure.

Documentation test subset (test_docs_consistency, test_integration_documentation, test_release_metadata): 12 passed. YAML re-parsed clean after the ci.yml comment edit.
<!-- SECTION:FINAL_SUMMARY:END -->
