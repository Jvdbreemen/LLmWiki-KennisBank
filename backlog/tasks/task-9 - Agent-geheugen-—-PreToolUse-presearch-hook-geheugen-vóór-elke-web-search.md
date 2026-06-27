---
id: TASK-9
title: Agent-geheugen — PreToolUse presearch-hook (geheugen vóór elke web-search)
status: In Progress
assignee: []
created_date: '2026-06-27 12:39'
updated_date: '2026-06-27 12:41'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies: []
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
kb-presearch.py: PreToolUse-hook die vuurt op WebSearch/WebFetch. Haalt de query/url uit tool_input, embedt 'm, draait kb-recall.memory_hits + wiki-zoek, en injecteert de hits als additionalContext VÓÓR de search loopt. Zo checkt de agent altijd eerst z'n eigen geheugen bij mid-turn zoekacties (UserPromptSubmit dekt alleen turn-start). Gegate op memory_recall, fail-open (nooit de tool blokkeren/vertragen), niet-blokkerend (geen deny). Hergebruikt kb-recall (fase 3). Registratie in ~/.claude/settings.json onder PreToolUse (matcher WebSearch|WebFetch), gedocumenteerd in CONFIGURATION.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kb-presearch.py vuurt op WebSearch/WebFetch, extraheert query/url uit tool_input
- [ ] #2 Injecteert memory+wiki-hits als additionalContext vóór de search (push)
- [ ] #3 Gegate op memory_recall; fail-open (exit 0, nooit blokkeren); geen echt model in tests
- [ ] #4 Geregistreerd + gedocumenteerd (PreToolUse matcher WebSearch|WebFetch)
<!-- AC:END -->
