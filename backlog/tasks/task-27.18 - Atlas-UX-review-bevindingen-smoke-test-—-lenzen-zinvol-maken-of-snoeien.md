---
id: TASK-27.18
title: 'Atlas: UX-review bevindingen smoke-test — lenzen zinvol maken of snoeien'
status: In Progress
assignee: []
created_date: '2026-07-14 17:53'
updated_date: '2026-07-14 18:03'
labels:
  - atlas
  - ux
  - review
dependencies: []
parent_task_id: TASK-27
priority: medium
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bevindingen van Robert tijdens de eerste echte smoke-test van de standalone app (2026-07-14). Kern: meerdere lenzen tonen data zonder handelingsperspectief. Per lens beslissen: zinvol maken (drill-down, actie-pad) of weglaten (KISS, noord-ster: uit de weg).

1. Quarantaine-queue zegt "mens beslist" maar biedt geen interface om te beslissen. Atlas is bewust read-only; besluit loopt nu via de janitor/re-judge of handmatig frontmatter wijzigen. Beslissen: approve/reject-knoppen in Atlas (eerste write-pad — design-beslissing + ADR) of de tekst eerlijk maken ("beslissen gebeurt via /kennisbank:settings / re-judge") met uitleg.
2. Timeline is betekenisloos: alleen event-tijd-balkjes, capture-serie leeg, geen drill-down. Onderzoeken hoe relevant te maken (klikbare week-buckets naar activity-events "wat deed ik toen", topic-overlay, koppeling met /watdeedik) — anders lens verwijderen.
3. Provenance bleef eenmalig hangen op "provenance laden…" (in andere sessies laadt hij in ~2s) — reproduceren en onderzoeken. Plus fundamenteler: 98%-dekking zonder actie-pad is een vanity metric; wat is de vervolgactie bij een unsourced artikel?
4. Supersede-ketens tonen rauwe [[wikilink]]-syntax (niet gerenderd, niet klikbaar) en verwijzen naar targets die niet als node/artikel gelinkt zijn — tweede kolom oogt daardoor vreemd. Renderen als klikbare items + target-bestaan valideren.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Per lens (Timeline, Provenance, Memory Health-queue, supersede-ketens) een expliciete beslissing vastgelegd: verbeteren met welk handelingsperspectief, of verwijderen
- [ ] #2 Quarantaine-queue: óf werkende beslis-interface óf eerlijke tekst met verwijzing naar het echte beslispad
- [ ] #3 Timeline: drill-down naar onderliggende activity-events of lens verwijderd
- [ ] #4 Provenance-hang gereproduceerd en verklaard of als niet-reproduceerbaar gedocumenteerd
- [ ] #5 Supersede-ketens: klikbare, gerenderde verwijzingen zonder rauwe [[...]]-syntax
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Besluiten Robert (2026-07-14): (1) approve/reject-knoppen in Atlas — eerste bewuste write-pad, begrensd tot statuswijziging van unverified memory-fragmenten; (2) Timeline-lens weglaten; (3) Provenance-lens weglaten, vervangen door nieuw Overzicht/health-lens met metrics over memories, wiki, raw logs, inbox (input waiting), provenance als één regel; (4) supersede-ketens fixen (klikbaar, geen rauwe [[...]], target-validatie) of weglaten — wordt: fixen.

Janitor/re-judge-triggering uitgezocht: memory-sweep.py draait autonoom (opt-in via kennisbank-settings, hook-gedreven) en zet fail-safe unverified bij twijfel of LLM-outage; de backlog her-beoordelen gaat met `python3 $VAULT/.claude/scripts/memory-doctor.py rejudge` (promoot naar current bij expliciet verdict, daarna build-kb-index voor recall).
<!-- SECTION:NOTES:END -->
