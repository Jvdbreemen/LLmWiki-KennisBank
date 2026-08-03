---
id: TASK-130
title: 'kb-lint.py: collect_session_stems() rglob''s the entire vault, not just 01-raw'
status: To Do
assignee: []
created_date: '2026-08-03 21:56'
labels:
  - performance
  - kb-lint
  - atlas
dependencies: []
priority: medium
ordinal: 125700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Discovered while measuring TASK-91 AC#8: Atlas sidecar's `/overview` endpoint calls `build_provenance()` -> `kb_lint.lint_vault()` on every request, uncached. On the real vault this alone took ~12.2s of the endpoint's ~13-14.6s total (measured 2026-08-03).

Root cause: `collect_session_stems()` (scripts/kb-lint.py:95) does `root.rglob(f"{SESSION_PREFIX}*.md")` -- a recursive walk over the WHOLE vault tree (09-memory, okf-out, archive, everything), not scoped to 01-raw/01-raw-adjacent dirs, even though its own docstring says the intent is "sessions moved to 01-raw/debug, 08-archive, ...". A vault with thousands of total files pays a full recursive filesystem walk on every lint_vault() call.

Atlas's own /overview got a stopgap fix (a 30s in-process TTL cache around build_overview, atlas/sidecar/sources.py) so the sidecar itself no longer pays this per-request. kb-lint.py itself (used directly by /wiki, doctor.sh, etc.) is unaffected by that cache and still pays the full rglob every invocation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Root cause confirmed: profile collect_session_stems() in isolation on the real vault, record ms
- [ ] #2 Fix scopes the walk (e.g. glob only under known session-bearing dirs, or cache the stems set with a cheap staleness check) without changing lint_vault()'s public contract
- [ ] #3 Re-measure build_provenance() / kb-lint on the real vault after the fix and record before/after here
- [ ] #4 Existing kb-lint tests stay green; add a regression test if the scoped walk could silently drop a valid session dir
<!-- AC:END -->
