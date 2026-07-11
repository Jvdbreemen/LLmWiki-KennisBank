---
id: TASK-27.4
title: Atlas - Graph-lens (wiki+memory nodes, encoding, click-to-inspect)
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - graph
  - lens
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: high
ordinal: 31400
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implementeer de Graph-lens: een force-directed graph van wiki- en
memory-nodes met betekenisvolle visuele encoding en een inspect-panel.

Nodes: wiki-artikelen (`layer: wiki`) en memories (`layer: memory`).
Edges: `[[wikilinks]]` + graphify `relation`/`confidence_score` + per-kernpunt
provenance-links (memory/wiki -> raw-sessie/bron).

Visuele encoding (mapt op echte velden uit 26.2):
- Kleur = `memory_type`/`layer` (feit/voorkeur/procedure/beslissing + wiki).
- Grootte = `importance` (1-5).
- Halo/gloed = usage warmth (`last_used` recency + injected/used ratio).
- Rand/stroke = `status` (current/unverified/superseded/...).
- Edge-dikte/opacity = graph `confidence_score` waar aanwezig.

Interactie:
- Drag, zoom, pan.
- Click-to-inspect panel: toont titel, type, status, importance, valid_from/
  valid_until, evidence/provenance en **links terug naar het bronbestand**
  (relatief pad in de vault) plus de raw-sessie/bron-herkomst.
- Legenda die elke encoding uitlegt.
- Basis-filter: op layer en op `status` (bv. verberg superseded).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De Graph-lens rendert nodes voor wiki en memory en edges uit wikilinks/graph/provenance. Bewijs: Playwright-test op een fixture telt gerenderde nodes/edges en matcht de JSON-tellingen.
- [ ] #2 Elke encoding is aantoonbaar datagedreven: kleur=type/layer, grootte=importance, halo=warmth, rand=status. Bewijs: test inspecteert de DOM/attributen van een bekende node en verifieert dat kleur/grootte/rand overeenkomen met diens frontmatter.
- [ ] #3 Click-to-inspect toont de nodedetails en een klikbaar/kopieerbaar bronpad + provenance. Bewijs: test klikt een node, verifieert dat het panel het juiste bronpad en valid_from/valid_until toont dat overeenkomt met de fixture.
- [ ] #4 Een legenda verklaart alle encodings; filters op layer/status werken. Bewijs: test toggelt "verberg superseded" en verifieert dat die nodes verdwijnen.
- [ ] #5 Performance: de lens rendert een vault-schaal fixture (zie 26.11 budget) zonder de UI te bevriezen. Bewijs: render-tijd gemeten onder het afgesproken budget.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Playwright-test (offline, `file://`) dekt render, encoding-mapping, inspect-panel en filter; screenshot als bewijs.
- [ ] #2 Een verificatiescript vergelijkt de node-encoding in de DOM met een directe frontmatter-query op de fixture (geen hand-gecontroleerde vibes).
- [ ] #3 Geen console-errors; lege-graph fixture toont nette lege staat.
- [ ] #4 Encoding-keuzes zijn kleurenblind-vriendelijk en werken in light/dark.
<!-- DOD:END -->
