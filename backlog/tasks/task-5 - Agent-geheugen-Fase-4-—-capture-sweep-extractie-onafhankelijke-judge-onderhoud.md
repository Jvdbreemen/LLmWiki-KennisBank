---
id: TASK-5
title: >-
  Agent-geheugen Fase 4 — capture & sweep (extractie + onafhankelijke judge +
  onderhoud)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
  - TASK-4
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SessionStart-sweep (gegate op memory_capture): extraheer kandidaat-memories uit nieuwe transcripts, dedup, onafhankelijke verse-context judge (hoge zekerheid -> current, twijfel -> unverified), cross-memory onderhoud (supersede/expire/cluster + hercontrole). Trigger-agnostisch (SessionStart + /sessielog). render() input-hardening (uitgesteld uit fase 1). LET OP: judge-uitvoeringsmechanisme (detached/headless, niet-blokkerend bij SessionStart) eerst met advisor beslechten vóór planning. LLM-call als mockbare seam; deterministische plumbing unit-getest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sweep extraheert+judget nieuwe transcripts, verse-context (onafhankelijk van producent)
- [ ] #2 Judge faalt/twijfelt -> unverified (fail-safe), nooit direct current
- [ ] #3 Niet-blokkerend bij SessionStart (detached) -- onzichtbaar/snel
- [ ] #4 Cross-memory: supersede/expire/cluster + hercontrole van current
- [ ] #5 render() hardening: _yaml_list string-guard + YAML-escape title/source_session
- [ ] #6 Deterministische plumbing unit-getest; LLM-call mockbaar
<!-- AC:END -->
