---
id: TASK-27.11
title: Atlas - performance/scale hardening en visuele eval
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - performance
  - eval
dependencies:
  - TASK-27.3
parent_task_id: TASK-27
priority: medium
ordinal: 32100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Borg de noord-ster ("performance vóór alles", "off de hot path", sub-seconde
ophalen) voor de Atlas op vault-schaal, en voeg een lichte visuele
regressie-eval toe.

Onderdelen:
- Definieer een performance-budget: max generatietijd (write/idle-time) en max
  open/render-tijd voor een representatieve vault (bv. N wiki + M memory + K
  events; leg concrete N/M/K vast in de design-spec).
- Genereer een synthetische large-vault fixture om het budget te toetsen.
- Schaalgedrag: bij overschrijding van een node/edge-cap sampelt de Atlas
  deterministisch en **logt expliciet wat is weggelaten** (geen stille
  truncatie; conform "feitelijke output, geen cruft").
- HTML-omvang bewaken: cap op bestandsgrootte; waarschuw als de payload een
  grens overschrijdt.
- Lichte visuele eval: sla referentie-screenshots op per lens (offline,
  `file://`) en detecteer grote onbedoelde visuele regressies in CI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Er is een vastgelegd performance-budget (generatie + open/render) met concrete drempels. Bewijs: de drempels staan in de design-spec en een test meet en vergelijkt.
- [ ] #2 Generatie en open/render blijven binnen budget op de synthetische large-vault fixture. Bewijs: perf-test meet beide tijden en faalt bij overschrijding; meetwaarden gelogd.
- [ ] #3 Bij overschrijding van de node/edge-cap sampelt de Atlas deterministisch en logt de weggelaten hoeveelheid. Bewijs: test met een oversized fixture verifieert de sampling en de expliciete "weggelaten: X" melding.
- [ ] #4 HTML-omvang blijft onder de cap; overschrijding geeft een waarschuwing. Bewijs: test meet bestandsgrootte tegen de cap.
- [ ] #5 Visuele referentie-screenshots per lens bestaan en een regressietest signaleert grote afwijkingen. Bewijs: baseline-screenshots in de repo/CI en een vergelijkingsstap.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Perf-test (generatie + headless open) draait offline en rapporteert meetwaarden; faalt buiten budget.
- [ ] #2 Sampling is deterministisch (stabiele selectie) en de weglating is zichtbaar in UI-status en log.
- [ ] #3 Visuele baseline is gedocumenteerd en reproduceerbaar (Chromium op `/opt/pw-browsers`, vaste viewport).
- [ ] #4 Geen stille caps: elke begrenzing (top-N, sampling) wordt gelogd, conform de noord-ster.
<!-- DOD:END -->
