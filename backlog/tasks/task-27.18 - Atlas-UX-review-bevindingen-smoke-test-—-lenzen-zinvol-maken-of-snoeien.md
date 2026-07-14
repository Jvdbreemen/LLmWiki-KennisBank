---
id: TASK-27.18
title: 'Atlas: UX-review bevindingen smoke-test — lenzen zinvol maken of snoeien'
status: Done
assignee: []
created_date: '2026-07-14 17:53'
updated_date: '2026-07-14 18:23'
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
- [x] #1 Per lens (Timeline, Provenance, Memory Health-queue, supersede-ketens) een expliciete beslissing vastgelegd: verbeteren met welk handelingsperspectief, of verwijderen
- [x] #2 Quarantaine-queue: óf werkende beslis-interface óf eerlijke tekst met verwijzing naar het echte beslispad
- [x] #3 Timeline: drill-down naar onderliggende activity-events of lens verwijderd
- [x] #4 Provenance-hang gereproduceerd en verklaard of als niet-reproduceerbaar gedocumenteerd
- [x] #5 Supersede-ketens: klikbare, gerenderde verwijzingen zonder rauwe [[...]]-syntax
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Besluiten Robert (2026-07-14): (1) approve/reject-knoppen in Atlas — eerste bewuste write-pad, begrensd tot statuswijziging van unverified memory-fragmenten; (2) Timeline-lens weglaten; (3) Provenance-lens weglaten, vervangen door nieuw Overzicht/health-lens met metrics over memories, wiki, raw logs, inbox (input waiting), provenance als één regel; (4) supersede-ketens fixen (klikbaar, geen rauwe [[...]], target-validatie) of weglaten — wordt: fixen.

Janitor/re-judge-triggering uitgezocht: memory-sweep.py draait autonoom (opt-in via kennisbank-settings, hook-gedreven) en zet fail-safe unverified bij twijfel of LLM-outage; de backlog her-beoordelen gaat met `python3 $VAULT/.claude/scripts/memory-doctor.py rejudge` (promoot naar current bij expliciet verdict, daarna build-kb-index voor recall).

Geïmplementeerd in commit c8cfc48; bundle herbouwd (build 4, NSIS 20:16) en silent geïnstalleerd. E2e geverifieerd tegen de geïnstalleerde app (sidecar poort 43107): /overview aggregeert echte vault (101 wiki, 850 active / 29 unverified memories, 797 sessielogs, 63 transcripts, inbox 1); POST /memory/decide getest met wegwerp-fragment (unverified → current, daarna opgeruimd — geen echte memories geraakt); screenshot toont werkende ✓/✗-knoppen in de app met live besliste items. 9 nieuwe sidecar-tests (46 totaal groen), frontend 32 groen. Bekende beperking: Overzicht wiki-by_status toont kb-index-status (alles 'current'), niet de frontmatter-status (actief/concept) — eventueel later frontmatter lezen. AC4 (Provenance-hang) blijft open: lens is verwijderd, maar de onderliggende /provenance-call wordt nog door /overview gebruikt; hang niet gereproduceerd.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Alle vier smoke-test-besluiten van Robert uitgevoerd en live bevestigd: (1) ✓/✗-beslisknoppen in de quarantaine-queue via POST /memory/decide — het enige bewuste write-pad in Atlas, begrensd tot de status-regel van unverified 09-memory-fragmenten (current/retracted, janitor-vocabulaire), traversal-guarded; (2) Timeline-lens verwijderd; (3) Provenance-lens verwijderd, vervangen door Overzicht-lens (eerste tab) met vault-brede health-metrics en herkomst als één regel; (4) supersede-ketens klikbaar met genormaliseerde stems en "(ontbreekt)"-markering. Provenance-hang niet gereproduceerd; gedocumenteerd — /overview gebruikt dezelfde call als toekomstig zoekpad. Commit c8cfc48, 46 sidecar- + 32 frontend-tests groen, bundle herbouwd en geïnstalleerd; Robert bevestigde werkende UX (fragmenten live goedgekeurd).
<!-- SECTION:FINAL_SUMMARY:END -->
