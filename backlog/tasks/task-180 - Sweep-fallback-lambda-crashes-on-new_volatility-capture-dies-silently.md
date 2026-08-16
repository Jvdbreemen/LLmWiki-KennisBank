---
id: TASK-180
title: Sweep fallback lambda crashes on new_volatility — capture dies silently
status: In Progress
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

memory-sweep.py:375 defines the partial-deploy fallback as
`lambda body, vf, vec, items: {"action": "ADD", ...}` while the call site
(line ~427) now passes `new_volatility=volatility`. When `import _reconcile`
or `import _maintenance` fails — the exact case the fallback exists for —
every candidate raises TypeError, the per-transcript `except Exception`
counts it as an error, and the sweep writes zero memories while reporting
only an error count: the silent capture outage the fallback's own comment
promises to prevent. The old fallback wrote everything as plain ADD.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Fallback accepts the same signature as _reconcile.reconcile (including new_volatility), returns ADD
- [ ] #2 A test simulates the failed-import path and asserts memories are still written as ADD
- [ ] #3 A grep-style guard or shared signature keeps fallback and real function from drifting again
<!-- AC:END -->
