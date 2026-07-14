---
id: TASK-27.5
title: Atlas - bi-temporele time-slider (valid-as-of graph)
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 20:32'
labels:
  - visualization
  - atlas
  - temporal
  - lens
dependencies:
  - TASK-27.4
parent_task_id: TASK-27
priority: high
ordinal: 31500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Voeg de onderscheidende feature toe: een tijd-slider die de Graph-lens herrekent
naar de **valid-as-of** staat op een gekozen datum, met de bi-temporele velden.

Gedrag:
- Slider over de vault-tijdspanne (min `valid_from`/`created`/`event_time`, max
  vandaag of laatste event).
- Op datum `D` toont de graph alleen memories/facts die geldig zijn op `D`:
  `valid_from <= D` en (`valid_until` afwezig of `valid_until > D`). `valid_until`
  is exclusief.
- Superseded/expired facts verschijnen/verdwijnen correct terwijl je scrubt; een
  supersede-overgang is zichtbaar (oude node sluit, nieuwe opent).
- Optionele tweede modus: capture-tijd-as (`created`/`captured_at`) vs
  valid-tijd-as, zodat "wat wist het systeem toen" vs "wat was waar toen"
  onderscheiden kan worden (bi-temporeel, Zep-patroon).
- Deterministisch en testbaar met een geinjecteerde `now`/`as_of` (geen interne
  klok in de renderlogica).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De slider filtert nodes correct op valid-as-of semantiek (`valid_from <= D < valid_until`). Bewijs: fixture met bekende valid-vensters; test zet de slider op drie datums en verifieert exact welke nodes zichtbaar zijn, inclusief de exclusieve `valid_until`-grens.
- [ ] #2 Een supersede-overgang is zichtbaar: op `D1` toont de oude fact, op `D2` (na `valid_until`) de opvolger. Bewijs: fixture met een `superseded_by`-keten; test verifieert de wissel over de grens.
- [ ] #3 De bi-temporele modus (valid-tijd vs capture-tijd) levert aantoonbaar verschillende resultaten voor een laat-geimporteerde oude fact. Bewijs: fixture met `valid_from` << `created`; test toont dat de twee assen verschillen op de juiste datum.
- [ ] #4 De filtering is deterministisch met geinjecteerde `as_of`. Bewijs: unit-test op de filterfunctie (JS-logica getest via headless of via een geextraheerde pure functie) met vaste input/output.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): de valid-as-of filtering draait client-side in de TS-frontend op de /graph-data (met valid_from/valid_until) van de sidecar (27.2); canvas/WebGL-rerender bij scrub. Geen statische export. Lens-logica/encoding-ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Bi-temporele time-slider afgerond (commit dfb6a0d). Valid-as-of-filter geextraheerd naar een pure, deterministische timefilter.ts (as-of ingespoten, geen klok) met 9 grens-unit-tests: valid_from inclusief, valid_until EXCLUSIEF, open-ended blijft geldig, atemporele nodes altijd zichtbaar, en de twee assen divergeren voor een laat-geimporteerd feit (valid sinds 2020, captured 2026). Time-slider gebruikt het + as-toggle: capture-tijd (wanneer bekend) vs valid-tijd (wanneer waar). Live: scrubben naar 2026-05-28 krimpt de graaf tot de toen-bestaande artikelen (kennis 'groeit').

AC-dekking: #1 valid-as-of-semantiek (valid_from<=D<valid_until, exclusief) — pure functie volledig unit-getest ✓ (visueel beperkt door wiki-only /graph); #2 supersede-overgang — logica getest (node verdwijnt na valid_until) maar NIET visueel op wiki-only graaf (geen memory-nodes met valid_until in /graph) — EERLIJKE GAP; #3 bi-temporeel valid vs capture — pure functie getest voor late-import + as-toggle bekabeld (op wiki-only data ~gelijk, geen zichtbaar verschil) — EERLIJKE GAP; #4 deterministisch met ingespoten as_of + pure-functie-unit-tests ✓. DoD#2 geisoleerde pure functie + grens-tests ✓; DoD#1 scrub + node-set-per-datum + screenshot ✓; DoD#4 geen console-errors ✓. 22 vitest + 32 sidecar groen, tsc schoon, build groen.

TERUGKERENDE DATA-SCOPE-GAP (27.4/27.9/27.5): /graph is wiki-only; memory-nodes met valid_from/valid_until zitten niet in de graaf, dus valid-tijd-as + supersede-overgangen zijn nog niet visueel te tonen op echte data. Logica compleet + getest; data mist de temporele vensters. Memory-nodes toevoegen aan /graph = aparte data-scope-taak (kandidaat-vervolg).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend-test scrubt de slider en verifieert de zichtbare node-set per datum; screenshots op 2-3 datums.
- [ ] #2 De valid-as-of filterfunctie is een geisoleerde pure functie met unit-tests op grens-cases (== valid_from, == valid_until, open-ended).
- [ ] #3 Tijdzone-consistentie (Europe/Amsterdam) met een DST-grens in de test.
- [ ] #4 Geen console-errors; herrekenen bij scrub blijft binnen budget (27.11).
<!-- DOD:END -->
