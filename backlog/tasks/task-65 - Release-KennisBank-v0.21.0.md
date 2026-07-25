---
id: TASK-65
title: Release KennisBank v0.21.0
status: In Progress
assignee: []
created_date: '2026-07-25 07:07'
labels:
  - release
dependencies: []
priority: high
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Uitbrengen van de vier structurele wijzigingen die de v0.20.0-analyse identificeerde maar bewust buiten die release liet: TASK-61 (relevantiepoort), TASK-62 (JSON-cache van de hot path), TASK-63 (SessionStart detachen), TASK-64 (hook-plafond en lockstaleness), plus TASK-58 (release-skill).

Minor, niet patch: twee feat-commits, een index-invalidatie die op elke vault één herbouw forceert, en een SessionStart die fundamenteel anders loopt. Niets breekt aan de CLI, de commands of de vault-indeling.

Deze release is tegelijk de eerste toepassing van de nieuwe release-skill. Elke stap die vaag, fout of onvolledig blijkt wordt in dezelfde release gecorrigeerd — dat is de reden om hem juist nu te gebruiken, terwijl er nog iemand is om hem te repareren.

Beslissingen van de gebruiker: releasen en daarna meten (niet vooraf), en de skill volgen in plaats van handmatig herhalen.

Openstaand na deze release: de relevantiedrempel van 0,60 is niet gemeten. `kb-eval` vereist een echte vault met lokaal embedmodel; CI heeft dat niet. De hits dragen nu `cos` en `fts` zodat de harnas de drempel kán meten, en `KB_RETRIEVE_THRESHOLD` plus `memory_threshold` stellen hem bij zonder herbouw.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De volledige testsuite is groen op de code die uitgebracht wordt, vóór de documentatie-edits
- [ ] #2 CHANGELOG heeft een 0.21.0-sectie met bijgewerkte compare-links, en beide README-varianten noemen dezelfde versie
- [ ] #3 De documentatie-subset is groen na de README- en changelog-edits
- [ ] #4 Er is een pull request naar upstream met een beschrijving die de dragende wijzigingen benoemt
- [ ] #5 De Copilot-review is opgehaald via de api-route en elke opmerking is getoetst aan code of meting vóór de merge
- [ ] #6 Na de merge is vastgesteld dat origin/main de commits feitelijk bevat, en de tag staat op die SHA
- [ ] #7 De gepubliceerde release-notes zijn niet leeg, geverifieerd via gh release view
- [ ] #8 Elke wrijving in de release-skill is in deze release zelf gecorrigeerd
- [ ] #9 TASK-58 en TASK-61 t/m 64 staan op Done
<!-- AC:END -->
