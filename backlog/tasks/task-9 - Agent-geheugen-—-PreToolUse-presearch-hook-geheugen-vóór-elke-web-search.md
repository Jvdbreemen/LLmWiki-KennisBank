---
id: TASK-9
title: Agent-geheugen — PreToolUse presearch-hook (geheugen vóór elke web-search)
status: Done
assignee: []
created_date: '2026-06-27 12:39'
updated_date: '2026-06-27 13:17'
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
- [x] #1 kb-presearch.py vuurt op WebSearch/WebFetch, extraheert query/url uit tool_input
- [x] #2 Injecteert memory+wiki-hits als additionalContext vóór de search (push)
- [x] #3 Gegate op memory_recall; fail-open (exit 0, nooit blokkeren); geen echt model in tests
- [x] #4 Geregistreerd + gedocumenteerd (PreToolUse matcher WebSearch|WebFetch)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase A afgerond. kb-recall.recall_hits (laag-generiek, beide lagen, memory-only live-recheck; memory_hits wrapper) + kb-presearch.py PreToolUse-hook (WebSearch/WebFetch, embedt query, injecteert memory+wiki-hits als additionalContext permissionDecision=defer, niet-blokkerend, fail-open, gegate op memory_recall). Commits df4d151, 0404b0d, 9462a5a, 3599680 + review-fix 4a7be7d. 233 tests groen. E2E-bewezen tegen echte index: WebSearch-payload -> injecteert relevante memories (defer), non-search tool stil. Whole-branch review: Ready=Yes, alle fail-open-paden geverifieerd, nooit deny, decoupling schoon. Garandeert nu: agent checkt eigen geheugen+wiki ZOWEL bij turn-start (UserPromptSubmit) ALS bij elke externe zoekactie (PreToolUse).
<!-- SECTION:FINAL_SUMMARY:END -->
