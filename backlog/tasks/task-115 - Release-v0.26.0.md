---
id: TASK-115
title: Release v0.26.0
status: Done
assignee: []
created_date: '2026-07-30 05:47'
updated_date: '2026-07-30 05:56'
labels: []
dependencies: []
ordinal: 113700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Minor release carrying the C4 architecture documentation set (TASK-98) and the MCP surface work that precedes the SDK bump (TASK-101, 102, 104, 105, plus TASK-108 partially). Notably NOT carrying the mcp>=2 pin bump: that is gated on observing a client that actually speaks 2026-07-28, because a modern-only server dies against every client currently in use (TASK-110). Minor rather than patch: tool annotations and the instructions carrier change observable server behaviour, the README primitive count is corrected, and a new documentation tree lands.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released v0.26.0 (tag 517c597, verified equal to origin/main after merging PR #90). Carries the C4 architecture documentation set and the MCP surface work that precedes the SDK bump. Gates: CI green on both PR #89 and PR #90; documentation subset 56 passed; release notes published and verified non-empty (4582 bytes). The mcp>=2 pin bump is explicitly excluded and the changelog says so with the measurement behind it. Local full suite showed 5 failures in test_setup_deploy.py that pass 22/22 in isolation and pass on Linux CI; recorded as TASK-116 rather than dismissed. Copilot review unavailable on this PR as on every PR today (account quota limit), so the merge rests on green CI, the local targeted suites and wire-level evidence instead.
<!-- SECTION:FINAL_SUMMARY:END -->
