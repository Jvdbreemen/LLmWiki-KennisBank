---
id: TASK-8
title: Agent-geheugen — Cross-memory onderhoud v2 (supersede/cluster/hercontrole)
status: To Do
assignee: []
created_date: '2026-06-27 11:24'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-5.2
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Uit het ontwerp (spec component 7), bewust LICHT in fase 4b v1 (alleen deterministische expire-pass gebouwd). V2 voegt toe: (1) SUPERSEDE - een nieuwe current die een bestaande current tegenspreekt -> oude status superseded + superseded_by-link (LLM-oordeel of high-cosine + judge); (2) CLUSTER - markeer gerelateerde current memories als promotie-kandidaat voor /wiki; (3) 2e-VERDEDIGINGSLINIE - hercontroleer recent gepromote current memories, kan alsnog retracten/superseden. Allemaal via de mockbare _judge/_llm-seams; deterministische plumbing unit-getest. Draait in de sweep (memory-sweep.py) als extra onderhoudspas, off hot path.
<!-- SECTION:DESCRIPTION:END -->
