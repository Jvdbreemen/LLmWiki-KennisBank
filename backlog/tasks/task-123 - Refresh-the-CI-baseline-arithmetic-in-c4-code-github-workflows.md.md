---
id: TASK-123
title: Refresh the CI baseline arithmetic in c4-code-github-workflows.md
status: To Do
assignee: []
created_date: '2026-07-30 19:12'
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
- [ ] #1 All five occurrences of 1099 reflect a freshly measured collect-only count, with the measurement command and its result recorded
- [ ] #2 The growth percentage against the ci.yml baseline of 781 is recomputed from the new figure
- [ ] #3 The document says how it expects to age, so the next reader knows whether a mismatch is a defect or expected drift
- [ ] #4 Consider whether ci.yml:10-16 should carry the corrected baseline, since that comment is the artefact the finding is actually about
<!-- AC:END -->
