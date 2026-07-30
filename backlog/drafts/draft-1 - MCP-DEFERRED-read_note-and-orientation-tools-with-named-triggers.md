---
id: DRAFT-1
title: 'MCP [DEFERRED]: read_note and orientation tools, with named triggers'
status: Draft
assignee: []
created_date: '2026-07-29 22:49'
updated_date: '2026-07-30 05:30'
labels: []
dependencies:
  - TASK-103
ordinal: 109700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DEFERRED by the definitive plan, not rejected. The final tool-surface analysis (docs/superpowers/plans/mcp-2026-07-28-migration.md section 6) keeps the surface at 8 tools + 1 resource and adds nothing, because each addition must earn its surface area. read_note: most of its argument is discharged by making recall emit vault-relative paths instead of bare [[wikilinks]], which a client can already open; revisit if a client is observed unable to act on those paths. orientation: revisit when a hookless client is actually in daily use, since today every client in use gets its orientation through the SessionStart hook. capture provenance parameters are tracked separately in TASK-107. Deliberately rejected rather than deferred: consolidating the four activity tools into one, which would break six shipped client configs for a cosmetic win, and structured output for recall, which doubles hot-path tokens for a consumer that does not exist.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 read_note tool added, read-only, resolves a wiki/memory stem to its content
- [ ] #2 orientation tool added, read-only, backed by kb-orientation.py
- [ ] #3 Both registered with English descriptions and readOnlyHint annotations
- [ ] #4 tools/list now returns ten tools and the harness asserts the exact set
- [ ] #5 No existing tool name or parameter changed
- [ ] #6 pytest suite green
<!-- AC:END -->
