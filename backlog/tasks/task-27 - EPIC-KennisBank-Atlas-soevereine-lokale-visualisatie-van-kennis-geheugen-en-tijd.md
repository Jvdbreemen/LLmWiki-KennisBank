---
id: TASK-27
title: >-
  EPIC: KennisBank Atlas - soevereine, lokale visualisatie van kennis, geheugen
  en tijd
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - epic
  - visualization
  - atlas
  - memory
  - wiki
  - temporal
references:
  - 'docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md'
  - 'https://arxiv.org/abs/2501.13956'
  - 'https://github.com/getzep/graphiti'
  - 'https://github.com/vladignatyev/brain-map-skill'
  - 'https://github.com/rohitg00/agentmemory'
  - 'https://github.com/sachitrafa/YourMemory'
  - 'https://mem0.ai/blog/graph-memory-solutions-ai-agents'
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Epic: KennisBank Atlas.

Doel: geef een mens een soevereine, lokale manier om de kennis (`02-wiki`), het
geheugen (`09-memory`) en de temporele dimensie (`kb-activity.db`) van
KennisBank te bekijken, zonder Obsidian, zonder externe plugin, zonder server en
zonder cloud.

Probleem (zie design/onderzoek in
`docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md`):
de repo produceert vandaag geen enkel visueel artefact. Alles is CLI-tekst,
markdown of een SQLite-index. De enige visuele surfaces zijn Obsidian (extern,
closed-source, graph leeg tot er wikilinks zijn, geheugen ongedifferentieerd) en
de externe Understand-Anything plugin. De rijk gestructureerde geheugenlaag
(typed, bi-temporeel, importance, status, evidence/trust) wordt nergens
gevisualiseerd, terwijl juist die de editor-in-chief moet kunnen overzien.

Oplossing: één gegenereerd, self-contained `atlas.html` in `<vault>/.claude/`,
regenereerd off de hot path (een `/atlas` command en een optionele idle-hook in
de stijl van `daily_graphify`). Eén deterministische export + één renderer, met
meerdere lenzen op dezelfde data (KISS): Graph, Time-slider (bi-temporeel),
Memory Health, Timeline, Recall Inspector en een Provenance/trust-overlay.

Join-key over alle stores is het bestandspad: `docs.path` (kb-index) =
`activity_events.source_path` = graphify node `source_file` = usage `stem`.

Inspiratie uit onderzoek:
- Zep/Graphiti: tijd als first-class as; "wat was waar op datum X" via
  valid_from/valid_until; provenance naar bron-episodes.
- brain-map-skill: markdown-map naar één self-contained interactieve HTML met
  force-graph, growth-timeline scrubber en click-to-inspect.
- agentmemory: memory browser, health dashboard en retrieval-waterfall die
  uitlegt waarom iets is opgehaald.
- YourMemory/Mem0: geheugen als decay x importance x warmth (mapt op `_rank.py`
  en usage-telemetrie).

Niet-doel:
- Geen hosted platform, geen verplichte graph database, geen netwerkbinding.
- Geen afhankelijkheid van Obsidian of Understand-Anything voor de basiswerking.
- Geen "vat alles samen" view zonder bewijslinks; elke node/panel moet terug
  naar een bronfile of event.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Er is een geneste backlog onder deze epic die design/ADR, data-export, generator, elke lens, command/hook/doctor/docs en performance-hardening dekt; elke child heeft concrete AC en een bewijs/verificatie-eis. Bewijs: `ls backlog/tasks/task-27.*` toont de children en elke child bevat een AC- en DoD-blok.
- [ ] #2 `/atlas` genereert een self-contained `<vault>/.claude/atlas.html` dat volledig offline over `file://` opent (geen netwerk-requests, geen CDN). Bewijs: genereer het bestand, open het met netwerk uit / devtools-network leeg, log toont 0 externe requests.
- [ ] #3 De Atlas toont minimaal de Graph-lens met wiki+memory nodes, de bi-temporele Time-slider en de Memory Health-lens; encodings mappen aantoonbaar op de echte frontmatter/DB-velden. Bewijs: per lens een verificatietest die renderdata vergelijkt met een directe query op bron.
- [ ] #4 De oplossing behoudt de noord-ster: local-first, no-cloud default, file/SQLite-based, off de hot path gegenereerd, sub-seconde te openen, auditeerbaar via source-provenance, fail-open bij ontbrekende index/model. Bewijs: doctor-check + performance-budget test uit de child-taken zijn groen.
- [ ] #5 De epic blijft open tot alle children Done zijn en `doctor.sh` de Atlas-status rapporteert (aanwezig/vers/stale). Bewijs: `doctor.sh` output bevat een atlas-regel.
<!-- AC:END -->

## Implementation Plan
<!-- SECTION:PLAN:BEGIN -->
Volgorde en afhankelijkheden:
1. TASK-27.1 Design + ADR (poort voor de rest).
2. TASK-27.2 Deterministische data-export naar canonical JSON.
3. TASK-27.3 Self-contained generator + tab-shell.
4. TASK-27.4 Graph-lens -> TASK-27.5 Time-slider, TASK-27.9 Provenance-overlay.
5. TASK-27.6 Memory Health, TASK-27.7 Timeline, TASK-27.8 Recall Inspector
   (parallel, hangen aan de shell 26.3).
6. TASK-27.10 Command + idle-hook + doctor + setup + docs (MVP-poort = 26.4).
7. TASK-27.11 Performance & scale hardening + visuele eval.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Alle child-taken (TASK-27.1 t/m TASK-27.11) zijn Done met hun eigen bewijs.
- [ ] #2 `/atlas` is geinstalleerd voor de geselecteerde agents en gedocumenteerd in README/OBSIDIAN/vault-structure waar relevant.
- [ ] #3 `doctor.sh` detecteert aanwezigheid en staleness van `atlas.html`.
- [ ] #4 Geen enkele clouddependency of netwerkbinding is toegevoegd; de generator is stdlib-first en de HTML is volledig self-contained.
<!-- DOD:END -->
