---
id: TASK-38
title: Restoring wiki provenance for upgrade validation
status: Done
assignee: []
created_date: '2026-07-19 22:04'
updated_date: '2026-07-19 22:07'
labels: []
milestone: v0.17.1
dependencies: []
priority: medium
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Trace local raw-session or source evidence for five wiki articles that block the KennisBank v0.17.1 doctor check. Add only verifiable provenance links, rerun strict lint, and finalize the pending release stamp.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each changed wiki article links to verified local provenance
- [x] #2 kb-lint.py --strict passes
- [x] #3 The KennisBank release stamp is updated only after doctor passes
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Verified and linked the 18 July and 19 July raw sessions for all five blocked wiki articles. Strict provenance lint and the v0.17.1 doctor check now pass; the release stamp is v0.17.1 (b5d5a10).
<!-- SECTION:FINAL_SUMMARY:END -->
