---
id: TASK-187
title: Overview TTL cache ignores the today parameter
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

atlas/sidecar/sources.py:975: _OVERVIEW_CACHE is keyed on str(vault) only,
while build_overview(vault, *, today=...) still accepts and forwards
`today`. Any two calls within the 30s TTL with different dates — tests
driving pinned dates, or a long-lived sidecar crossing midnight — return
the payload computed for the other date: staleness windows, rot counts
and the heatmap cutoff silently wrong, the parameter dead on every hit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Cache key includes the effective date (or today invalidates the entry)
- [ ] #2 A test calls build_overview twice within TTL with different dates and asserts distinct payloads
<!-- AC:END -->
