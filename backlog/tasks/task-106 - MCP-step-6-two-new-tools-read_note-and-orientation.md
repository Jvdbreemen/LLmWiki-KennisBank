---
id: TASK-106
title: 'MCP step 6: two new tools, read_note and orientation'
status: To Do
assignee: []
created_date: '2026-07-29 22:49'
labels: []
dependencies:
  - TASK-103
ordinal: 109700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Plan §3.2 step 6 and §6. Tool surface goes from 8 to 10; nothing is removed or renamed. read_note: recall returns [[wikilink]] references that six of the seven target clients cannot follow, so the link is a dead end — and a read is the only honest usage signal available on the MCP path, where no hook exists to record what got used. orientation: hookless clients start blind, because the vault orientation that Claude Code receives at SessionStart has no equivalent for a pull-only client; kb-orientation.py already produces exactly that summary. Both are read-only. Explicitly rejected in the same review: consolidating the four activity tools into one (would break six shipped client configs for a cosmetic win) and any tool that would let an agent promote its own knowledge (the human stays update authority).
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
