---
id: TASK-27.6
title: 'Atlas - Memory Health-lens (quarantaine, supersede-ketens, warmth)'
status: Done
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-12 17:33'
labels:
  - visualization
  - atlas
  - memory
  - lens
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: high
ordinal: 31600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw de editor-in-chief cockpit: een Memory Health-lens die de geheugenlaag
inzichtelijk maakt en het menselijke review-werk ondersteunt.

Onderdelen (uit memory-frontmatter + `kb-usage.db`):
- **Quarantaine-queue**: alle memories met `status: unverified` die op menselijke
  merge/reject wachten; sorteerbaar op `importance` en `created`.
- **Supersede-ketens**: `superseded_by`-relaties als kleine tijdlijnen (oude fact
  -> nieuwe fact, met `valid_until`), zodat je ziet wat waardoor is vervangen.
- **Importance x recency heatmap**: memories geplot op importance (1-5) tegen
  recency (leeftijd via `valid_from`/`created`), met de half-life-intuitie uit
  `_rank.py`.
- **Warm/stale**: warmth uit usage (`last_used`, injected/used ratio); markeer
  koude/stale memories en warme die recent nuttig waren.
- Elke rij linkt terug naar het bronbestand.

Deze lens visualiseert precies wat vandaag onzichtbaar is en operationaliseert
het principe "systeem stelt voor, mens beslist".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De quarantaine-queue toont exact de set `status: unverified` memories. Bewijs: test vergelijkt de gerenderde lijst met een directe frontmatter-query op de fixture; sets zijn gelijk.
- [ ] #2 Supersede-ketens renderen de juiste oude->nieuwe relaties met `valid_until`. Bewijs: fixture met een keten; test verifieert de getoonde volgorde en datums.
- [ ] #3 De importance x recency heatmap plot elke memory in de juiste cel. Bewijs: test controleert de cel-toewijzing van een bekende memory tegen zijn importance en leeftijd.
- [ ] #4 Warm/stale-markering matcht de usage-telemetrie. Bewijs: fixture-usage met bekende `last_used`; test verifieert dat de juiste memories warm/stale gemarkeerd zijn conform de drempels uit `_rank.py`/`_usage.py`.
- [ ] #5 Elke rij bevat een klikbaar/kopieerbaar bronpad. Bewijs: test verifieert het pad van een bekende rij.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TAURI RE-SCOPE (zie TASK-27 + 27.1-ADR): data LIVE van sidecar-endpoint /memory-health (27.2, hergebruikt _memory + usage); gerenderd in de TS-frontend. Quarantaine/supersede-ketens/warmth-heatmap komen uit de live-response, niet uit een statische export. Lens-logica/ACs blijven gelden.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Memory Health cockpit afgerond (commit be7c764). /memory-health uitgebreid met: quarantaine-queue (unverified, gesorteerd op importance), supersede-ketens met valid_until, importance×recency-heatmap-data, en warm/tepid/stale-temperatuur per warmth (drempels spiegelen _rank.usage_factor: ≤30d warm, ≤90d tepid). `today` injecteerbaar → deterministische, datum-relatieve tests (geldig ook tegen live instance). Frontend-lens: tiles, klikbare quarantaine-queue (→ bron-memory), 5×4 importance×recency-heatmap met intensiteit, warm/stale-badges, ketens met valid_until. ageBucket = pure unit-geteste helper.

AC-dekking: #1 queue == unverified (data-parity test) ✓; #2 ketens met valid_until ✓; #3 heatmap plaatst elke active memory in de juiste cel (test) ✓; #4 warm/stale per _rank-drempels ✓; #5 klikbaar bronpad ✓. Live: 753 active / 10 unverified-queue / heatmap (imp4,8-30d=395) / WARM-badges. 30 sidecar + 12 vitest groen, tsc schoon, build groen.

BONUS-FIX: race-bug die ALLE lenzen trof — een trage async-lens (Graph await /graph+/provenance) kon na een lens-switch resolven en de nieuwe lens-DOM overschrijven. Opgelost met een render-generatie (lifecycle.ts) die bij elke switch bumpt; withLoader + Graph-lens verwerpen hun resultaat als niet meer actueel.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend-test (dev-frontend + live sidecar) dekt queue, ketens, heatmap en warm/stale; screenshot als bewijs.
- [ ] #2 Data-parity: de lens-inhoud == directe queries op fixture-frontmatter + usage-DB (via het /memory-health endpoint).
- [ ] #3 Lege staat (geen unverified memories) toont een nette 'niets in quarantaine' boodschap.
- [ ] #4 Kleur/markering is kleurenblind-vriendelijk en werkt in light/dark.
<!-- DOD:END -->
