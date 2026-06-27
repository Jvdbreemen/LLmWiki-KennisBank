---
id: TASK-4
title: Agent-geheugen Fase 3 — recall (kb-recall + hook-gate + lokale MCP-server)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 08:10'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
kb-recall query-lib (hybride, beide lagen, current-only, recency-tiebreak) gebruikt door zowel de uitgebreide kb-retrieve hook (gegate op memory_recall) als een nieuwe lokale stdio MCP-server (Cursor/LM Studio/Claude Desktop). MCP-dep (mcp pip) is optioneel + fail-soft: ontbreekt 'ie, dan werkt de hook-recall gewoon door. Geen cloud-bind.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 kb-recall fuseert vector+FTS, beide lagen, filtert status!=current, recency-tiebreak
- [ ] #2 kb-retrieve hook injecteert memory alleen als memory_recall aan (anders enkel wiki, als nu)
- [ ] #3 Lokale stdio MCP-server exposeert recall; mcp-dep ontbreekt -> fail-soft, hook werkt door
- [ ] #4 Geen externe host-calls (no-cloud test)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Recall-pad besluit (advisor-bevestigd): ADDITIEF (2a), GEEN migratie. Laat het bestaande JSON-cosine wiki-pad in kb-retrieve.py ONGEMOEID; voeg memory-recall toe als additieve, memory_recall-gegate stap. De hook embedt de query al 1×; hergebruik die vector voor _kbindex.search(layers=("memory",), statuses=("current",)) en merge. Eén embed, twee lookups. Wiki-gedrag byte-identiek als memory uit -> behoudt de geteste 'memory off = byte-identiek'-invariant. 'Wiki eerst, memory niet begraven' = presentatie-volgorde, NIET een verenigde ranking (cosine vs RRF zijn niet op dezelfde schaal); thresholdt elke laag apart en presenteer wiki dan memory. Migratie van wiki-recall naar de hybride index = aparte latere fase met before/after-eval-gate, niet in fase 3 smokkelen.

MCP-server: APPROACH ok (optionele dep, fail-soft, stdio, lokaal) maar UITSTELLEN tot na fase 4 (MCP over lege memory-laag is niet e2e-testbaar; de kb-recall-lib levert ~alle waarde). Pitfalls: SQLite read-only openen (mode=ro/PRAGMA query_only; sweep is concurrent writer); 'db nog niet gebouwd' netjes afvangen; mcp-import achter try/except zodat afwezigheid de hook-recall + no-cloud/decoupling-tests nooit raakt; doctor no-cloud-check behandelt ontbrekende mcp als prima; dunne wrapper over kb-recall + embed-seam, unit-test de lib, smoke-test de wrapper. Fase 3 = kb-recall lib + hook-integratie; MCP-server-wrapper = na fase 4.
<!-- SECTION:NOTES:END -->
