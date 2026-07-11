---
id: TASK-27.1
title: Atlas - design spec en ADR voor self-contained lokale HTML-visualisatie
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - design
  - adr
dependencies: []
parent_task_id: TASK-27
priority: high
ordinal: 31100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Leg het ontwerp van de KennisBank Atlas vast en verhef de kernkeuzes tot een
ADR, zodat de bouwtaken een vaste, uitlegbare basis hebben.

Baseer op de research-synthese in
`docs/superpowers/specs/2026-07-11-knowledge-visualization-atlas-design.md` en
werk die uit tot een implementeerbaar contract.

Te beslissen en te documenteren:
- Rendermechanisme: één self-contained `atlas.html` met inline JS/CSS. Kies de
  graph-tech (bv. inline D3 v7 gevendord in-repo vs. vanilla canvas). Motiveer
  tegen de noord-ster (geen CDN, geen netwerk, klein, uitlegbaar).
- Regeneratiemodel: `/atlas` command + optionele idle-hook toggle in de stijl
  van `daily_graphify`; output naar `<vault>/.claude/atlas.html`; nooit op de
  interactieve hot path.
- Data-contract: canonical JSON tussen export (26.2) en renderer (26.3),
  inclusief de bestandspad-join (`docs.path` = `activity_events.source_path` =
  graphify `source_file` = usage `stem`) en de assen (categorisch, temporeel,
  gewicht/intensiteit) uit de design-spec.
- Lens-scope en prioriteit: Graph, Time-slider, Memory Health, Timeline, Recall
  Inspector, Provenance-overlay; welke zijn MVP en welke volgen.
- Fail-open gedrag: ontbrekende `kb-index.db`/`kb-activity.db`/`graph.json` mag
  de Atlas niet breken; lens toont een nette lege staat.
- Privacy/sovereignty: geen embeddings of ruwe transcripts in de HTML dumpen
  buiten wat nodig is; alles blijft lokaal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Een design-spec beschrijft het volledige Atlas-contract: rendermechanisme, regeneratiemodel, canonical JSON-schema, lens-scope/prioriteit, fail-open en privacygrenzen. Bewijs: het spec-bestand bestaat onder `docs/superpowers/specs/` en bevat elk van deze secties met kopjes.
- [ ] #2 Een ADR legt de bindende keuzes vast: (a) self-contained HTML zonder CDN/netwerk, (b) graph-tech keuze met alternatieven en motivatie, (c) generate-off-hot-path. Bewijs: het ADR-bestand bestaat onder `docs/adr/` met een oplopend nummer en de status is `accepted`.
- [ ] #3 Het canonical JSON-schema is expliciet (velden, types, join-key) en verwijst naar de exacte bronvelden per store. Bewijs: het schema in de spec noemt per veld de bron (`_memory.py`/`_activity.py`/`_kbindex.py`/`_usage.py`/`graph.json`).
- [ ] #4 De MVP-poort is vastgelegd: welke lenzen moeten werken voordat `/atlas` als bruikbaar geldt. Bewijs: de spec benoemt de MVP-lensset en dit komt overeen met de dependencies van TASK-27.10.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec en ADR zijn gereviewd en gecommit; de epic TASK-27 verwijst ernaar in references.
- [ ] #2 Elke latere bouwtaak (26.2-26.11) kan zijn AC herleiden tot een sectie in deze spec (traceerbaarheid). Bewijs: de spec bevat een tabel die lens/onderdeel aan child-taak koppelt.
- [ ] #3 Geen keuze in de ADR introduceert een cloud- of netwerkafhankelijkheid; dit is expliciet benoemd in de ADR-consequences.
<!-- DOD:END -->
