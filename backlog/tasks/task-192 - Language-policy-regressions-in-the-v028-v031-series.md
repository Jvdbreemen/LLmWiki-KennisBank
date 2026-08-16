---
id: TASK-192
title: Language policy regressions in the v0.28-v0.31 series
status: To Do
assignee: []
created_date: '2026-08-15 23:30'
updated_date: '2026-08-15 23:30'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the 2026-08-15 eight-angle /code-review over main...release/v0.31.1,
verified against source before filing. Task IDs 169-179 are reserved by the
open PR #2 branch; this series starts at 180.

CLAUDE.md: all documentation including code comments is English by
default; archived task-157 treats existing Dutch strings as debt. The
August series added new instances: kb-lint.py:90-95 and :106-112 (new
Dutch comment blocks), .github/workflows/ci.yml:18-19 (Dutch timeout
rationale), task-126 (Dutch-primary task document), task-145
implementation notes (Dutch paragraphs). Translate in place; no content
changes. The six unguarded parents[2] vault headers found in the same
sweep are already tracked as TASK-167 and the guard defect itself as
TASK-181 — not duplicated here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The named comments and documents are English; content unchanged
- [ ] #2 A lint check (or the existing task-157 tooling) covers new Dutch in scripts/ and .github/ so the debt stops regrowing
<!-- AC:END -->
