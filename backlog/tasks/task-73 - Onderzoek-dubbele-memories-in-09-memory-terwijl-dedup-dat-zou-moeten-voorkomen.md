---
id: TASK-73
title: >-
  Onderzoek: dubbele memories in 09-memory terwijl dedup dat zou moeten
  voorkomen
status: To Do
assignee: []
created_date: '2026-07-25 18:06'
updated_date: '2026-07-25 18:14'
labels:
  - bug
  - geheugen
  - retrieval
  - onderzoek
dependencies: []
priority: high
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bij de adversariele verificatie van TASK-72 kwam naar boven dat 09-memory letterlijke duplicaten bevat, allebei met status: current.

Concrete gevallen (gevonden door een verificatie-agent, niet door een gerichte zoektocht - er zijn er dus vermoedelijk meer):
- 2026-07-05-vmmemwsl-resource-accounting.md en -accounting-2.md: zelfde titel, zelfde body, beide current
- 2026-07-05-oorzaak-vmmemwsl-verbruik.md en -verbruik-2.md: idem
- 2026-07-02-esp32-s3-ble-scan-mode.md en 2026-07-02-passive-continuous-ble-scanning.md: near-duplicaat uit dezelfde bronsessie (2026-06-30-otgw-firmware-39cc00b2.jsonl), andere formulering, zelfde feit
- 2026-07-02-hybride-zoekstrategie-c-b.md naast -gebruik-van-sqlite-vec.md en -brute-force-knn-voor-kleine-datasets.md: overlappende inhoud uit dezelfde sessie

Waarom dit ertoe doet, en niet alleen cosmetisch is:
1. Retrieval kan tussen identieke documenten niet kiezen; ze verdunnen elkaars signaal en duwen elkaar uit de top-k. Plausibele mede-oorzaak van de 25 rang-0 gevallen uit TASK-72.
2. Het `-2`-achtervoegsel wijst op een slug-collision-afhandeling die een NIEUW bestand maakt in plaats van te herkennen dat de inhoud al bestaat. Schrijfpad-ontwerpfout, geen incident.
3. De vault bevat expliciete beslissingen tegen dubbele kennis: 2026-07-02-geen-wiki-naar-memory-seeding ('voorkomt dubbele kennis en bloat') en 2026-07-02-wiki-to-memory-seeden ('inclusief een deduplicatiecontrole'). De praktijk wijkt af van het vastgelegde ontwerp.

GEWENSTE EINDSITUATIE (gebruiker, 2026-07-25): er hoort een ontdubbelaar te zijn. Zodra een duplicaat wordt ontdekt moet er automatisch een geheugen-sweep draaien die een van de twee registraties opruimt. Dus niet alleen diagnose: het onderzoek moet uitmonden in een automatische, terugkerende ontdubbeling - conform het KennisBank-principe 'automatiseren boven handwerk' (CLAUDE.md), want wat handmatige discipline vereist gebeurt in de praktijk niet.

Te onderzoeken: welk schrijfpad maakt de duplicaten (capture bij SessionEnd, memory-sweep, rebuild-memory, een import-route, of meerdere), of er uberhaupt een dedup-controle bestaat op dat pad, en waarom die niet greep. Plus: bestaat er al een ontdubbelaar (find-similar.py doet semantische gelijkenis; memory-sweep.py draait periodiek) en waarom ruimt die niets op.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Omvang gemeten: aantal exacte duplicaten (identieke body na frontmatter) en near-duplicaten in 09-memory, met de volledige lijst
- [ ] #2 Het schrijfpad dat de duplicaten produceert is met bewijs aangewezen (file:line), niet op vermoeden
- [ ] #3 Vastgesteld of er een dedup-controle op dat pad bestaat en zo ja waarom die niet greep; zo nee, waarom hij ontbreekt
- [ ] #4 Verklaard waar het `-2`-achtervoegsel vandaan komt en welke functie die collision afhandelt
- [ ] #5 Bestaande hulpmiddelen getoetst: find-similar.py, conflict-scan.py, memory-sweep.py - hadden die dit moeten vangen, en waarom deden ze het niet
- [ ] #6 Onderscheid gemaakt tussen echte duplicaten (weg) en legitiem gesplitste memories uit dezelfde sessie (blijven); het criterium daarvoor is expliciet
- [ ] #7 AUTOMATISCHE ONTDUBBELING: memory-sweep ruimt duplicaten voortaan zelf op, zonder handmatige stap
- [ ] #8 Opruimen is veilig en omkeerbaar: de behouden memory verwijst naar de opgeruimde (superseded_by of gelijkwaardig), niets verdwijnt stilzwijgend
- [ ] #9 Voor- en nameting van recall@k op de TASK-72-sets, zodat de bewering 'duplicaten schaadden de retrieval' getoetst wordt in plaats van aangenomen
- [ ] #10 Vault-root via _vaultpath.vault_root(); tests in tests/; volledige suite groen
- [ ] #11 COLLISIE-CHECK BIJ SCHRIJVEN: als de slug al bestaat, wordt de genormaliseerde body vergeleken voordat een -2 wordt toegekend. Byte-identiek (na frontmatter) = het bestand wordt NIET aangemaakt en het bestaande pad wordt teruggegeven; alleen bij afwijkende inhoud volgt het volgnummer.
- [ ] #12 Vastgelegd wat er gebeurt bij identieke body maar afwijkende frontmatter (andere source_session, andere created): schrijven overslaan en herkomst samenvoegen, of toch apart houden - de keuze is expliciet en onderbouwd.
- [ ] #13 Expliciet vastgesteld dat de collisie-check alleen duplicaten met DEZELFDE slug vangt, en dat near-duplicaten met een andere titel (bv. esp32-s3-ble-scan-mode naast passive-continuous-ble-scanning) daar per definitie doorheen glippen; die vragen het sweep-mechanisme.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ONTWERPRICHTLIJN VAN DE GEBRUIKER (2026-07-25), leidend bij de beoordeling van het onderzoeksvoorstel:

Een naamcollisie is zelf het signaal. Op het moment dat de code een -2 wil toekennen, weet hij al dat er een gelijknamig bestand is. Precies daar hoort de inhoudsvergelijking, niet in een latere scan:

  slug bestaat al?
    -> body genormaliseerd vergelijken (na frontmatter)
       -> identiek  : NIET schrijven, bestaand pad teruggeven
       -> verschilt : pas dan -2, want het is echte andere kennis

Waarom dit de sterkste plek is: geen drempel, geen embedding, geen gok. O(1) en deterministisch, en het kan per constructie geen kennis weggooien - er stond al een byte-identieke kopie. Dat maakt het risicoprofiel fundamenteel anders dan een gelijkenis-sweep.

BELANGRIJKE BEPERKING, expliciet te noemen zodat de fix niet half blijft: dit vangt alleen duplicaten die DEZELFDE slug produceren. De ESP32-BLE-duplicaten (esp32-s3-ble-scan-mode naast passive-continuous-ble-scanning) hebben verschillende titels uit dezelfde sessie en botsen dus nooit. Twee mechanismen zijn nodig:
  - collisie-check bij schrijven -> exacte duplicaten, nul risico
  - sweep met gelijkenis        -> near-duplicaten, reeel risico, dus omkeerbaar via superseded_by
<!-- SECTION:NOTES:END -->
