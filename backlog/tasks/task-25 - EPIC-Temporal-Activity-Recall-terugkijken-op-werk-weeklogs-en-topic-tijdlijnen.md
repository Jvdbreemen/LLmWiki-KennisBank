---
id: TASK-25
title: >-
  EPIC: Temporal Activity Recall - terugkijken op werk, weeklogs en
  topic-tijdlijnen
status: Done
assignee: []
created_date: '2026-07-07 21:40'
updated_date: '2026-07-07 23:00'
labels:
  - epic
  - temporal-activity-recall
  - memory
  - mcp
  - commands
dependencies: []
references:
  - 'https://docs.mem0.ai/introduction'
  - 'https://arxiv.org/abs/2504.19413'
  - 'https://www.getzep.com/platform/graphiti/'
  - 'https://arxiv.org/html/2501.13956v1'
  - 'https://docs.letta.com/guides/core-concepts/stateful-agents/'
  - 'https://github.com/yoloshii/clawmem'
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Epic: Temporal Activity Recall.

Doel: maak KennisBank in staat om betrouwbaar terug te kijken in activiteit over tijd: "wat deed ik vorige week?", "wat deed ik op 2026-07-03?", "/timeline vorige week", "/weeklog", en topic-tijdlijnen zoals "volg het onderwerp Codex MCP door de tijd".

Scope:
- Bouw een lokale, soevereine activity-memory laag bovenop bestaande KennisBank bronnen: raw sessies, transcripts, 09-memory, wiki-artikelen, usage-telemetry en agent events.
- Maak tijd een first-class retrieval-as: event_time, captured_at, valid_from/valid_until, source/provenance, project/repo, actor/agent, topic/entities, artifact paths, decisions and outcomes.
- Exposeer dezelfde functionaliteit via slash/prompt commands en MCP tools, zodat Claude Code, Codex, OpenCode en andere lokale agents dezelfde API gebruiken.
- Houd alles lokaal, deterministic-first, auditeerbaar en fail-open. Geen cloudafhankelijkheid voor basiswerking.

Inspiratie uit onderzoek:
- Mem0: expliciete memory lifecycle, extraction/consolidation/retrieval en benchmarkdenken rond temporal/multi-hop vragen.
- Zep/Graphiti: temporele context graph, evoluerende facts, invalidatie van oude relaties, hybrid retrieval.
- Letta/MemGPT: stateful agent memory met persistent state, core/archival memory en memory editing/forgetting.
- ClawMem: on-device memory voor coding agents, MCP routing, query escalation en lifecycle controls.

Niet-doel:
- Geen hosted memory-platform introduceren als runtime dependency.
- Geen graph database verplicht maken; een lokaal SQLite-first ontwerp is de default tenzij een latere ADR hard bewijs geeft dat dit onvoldoende is.
- Geen vaag "samenvat alles" command zonder bewijslinks; elke output moet terug kunnen naar bronfiles/events.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een uitgewerkte, geneste backlog onder deze epic met architectuur, indexering, query parsing, commands, MCP API, rollups, evaluatie en setup/doctor taken.
- [x] #2 Elke child-taak bevat concrete acceptatiecriteria en test/validatieverwachtingen; geen taak mag alleen een onderzoeksnotitie zijn zonder bewijsbare uitkomst.
- [x] #3 De epic blijft open totdat /weeklog, /timeline en /watdeedik lokaal werken, de MCP server dezelfde retrieval-API biedt, en een temporal eval-harnas regressies kan meten.
- [x] #4 De oplossing behoudt KennisBank-principes: local-first, no-cloud default, file/SQLite based, auditeerbaar via source provenance, fail-open waar hooks of modellen falen.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Done: all TASK-25 child tasks are Done. Temporal Activity Recall is implemented end-to-end with design spec, activity event model/extractors, SQLite index, parser, API, commands, MCP tools, rollups, topic timelines, eval harness, setup/doctor integration and docs. Validation evidence: 60 targeted tests passed; live Kluis full rebuild indexed 6,564 events from 1,561 sources; live setup with model checks passed; doctor reported 102 PASS / 1 WARN / 0 FAIL; Codex MCP validation reported no errors.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Alle child-taken zijn Done of expliciet Blocked met reden en eigenaar.
- [x] #2 README, CONFIGURATION, AGENTS.md en relevante command docs beschrijven Temporal Activity Recall.
- [x] #3 Doctor/setup valideren de activity index, commands, MCP tools en minimaal een smoke recall query.
- [x] #4 Een release-note vermeldt het featurepakket en de migratie/upgrade-impact.
<!-- DOD:END -->
