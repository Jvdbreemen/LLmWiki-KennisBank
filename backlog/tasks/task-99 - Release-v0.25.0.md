---
id: TASK-99
title: Release v0.25.0
status: Done
assignee: []
created_date: '2026-07-29 21:26'
updated_date: '2026-07-29 21:37'
labels: []
dependencies: []
ordinal: 102700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Minor release carrying TASK-97: eval runs never write usage telemetry (KB_USAGE_DISABLE guard, unconditional, self-restoring, stderr framing) plus the doctor.sh warning for a stray KB_USAGE_DISABLE. Needed before upgrading the deployed vault, otherwise the deploy would land on v0.24.1 and lose the guard. Full suite green on the release code: 1097 passed, 2 skipped.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Released v0.25.0 (tag 970039f, verified equal to origin/main after merging PR #88). Carries TASK-97: an eval never counts as usage, plus the doctor.sh warning for a stray KB_USAGE_DISABLE. Gates: full suite 1097 passed / 2 skipped on the released code; documentation subset 56 passed; CI green (test + atlas). Release notes published, body verified non-empty (1822 bytes). Prepared in a clean git worktree because the main checkout held untracked generated C4 docs that trip two test_docs_consistency guards - one of them a genuine false positive, since build-karpathy-index.py really does print the [warn]/[error] markers the guard treats as invented doctor output; both tracked under TASK-98. Copilot review unavailable (account quota limit) on this PR as well as on #85 and #87 today.
<!-- SECTION:FINAL_SUMMARY:END -->
