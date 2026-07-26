---
id: TASK-73
title: >-
  Onderzoek: dubbele memories in 09-memory terwijl dedup dat zou moeten
  voorkomen
status: Done
assignee: []
created_date: '2026-07-25 18:06'
updated_date: '2026-07-26 09:55'
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
- [x] #1 Omvang gemeten: aantal exacte duplicaten (identieke body na frontmatter) en near-duplicaten in 09-memory, met de volledige lijst
- [x] #2 Het schrijfpad dat de duplicaten produceert is met bewijs aangewezen (file:line), niet op vermoeden
- [x] #3 Vastgesteld of er een dedup-controle op dat pad bestaat en zo ja waarom die niet greep; zo nee, waarom hij ontbreekt
- [x] #4 Verklaard waar het `-2`-achtervoegsel vandaan komt en welke functie die collision afhandelt
- [x] #5 Bestaande hulpmiddelen getoetst: find-similar.py, conflict-scan.py, memory-sweep.py - hadden die dit moeten vangen, en waarom deden ze het niet
- [x] #6 Onderscheid gemaakt tussen echte duplicaten (weg) en legitiem gesplitste memories uit dezelfde sessie (blijven); het criterium daarvoor is expliciet
- [x] #7 AUTOMATISCHE ONTDUBBELING: memory-sweep ruimt duplicaten voortaan zelf op, zonder handmatige stap
- [x] #8 Opruimen is veilig en omkeerbaar: de behouden memory verwijst naar de opgeruimde (superseded_by of gelijkwaardig), niets verdwijnt stilzwijgend
- [x] #9 Voor- en nameting van recall@k op de TASK-72-sets, zodat de bewering 'duplicaten schaadden de retrieval' getoetst wordt in plaats van aangenomen
- [x] #10 Vault-root via _vaultpath.vault_root(); tests in tests/; volledige suite groen
- [x] #11 COLLISIE-CHECK BIJ SCHRIJVEN: als de slug al bestaat, wordt de genormaliseerde body vergeleken voordat een -2 wordt toegekend. Byte-identiek (na frontmatter) = het bestand wordt NIET aangemaakt en het bestaande pad wordt teruggegeven; alleen bij afwijkende inhoud volgt het volgnummer.
- [x] #12 Vastgelegd wat er gebeurt bij identieke body maar afwijkende frontmatter (andere source_session, andere created): schrijven overslaan en herkomst samenvoegen, of toch apart houden - de keuze is expliciet en onderbouwd.
- [x] #13 Expliciet vastgesteld dat de collisie-check alleen duplicaten met DEZELFDE slug vangt, en dat near-duplicaten met een andere titel (bv. esp32-s3-ble-scan-mode naast passive-continuous-ble-scanning) daar per definitie doorheen glippen; die vragen het sweep-mechanisme.
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

UITGEVOERD 2026-07-26.

DRIE WIJZIGINGEN.

1. COLLISIE-CHECK (AC #11/#12/#13). unique_memory_path nummerde blind door zodra het pad bezet was. Nu wordt eerst de genormaliseerde body vergeleken; identiek = geen nieuw bestand, het bestaande pad komt terug en de sweep telt het als duplicaat. Signatuur geeft nu (pad, bestaat_al) terug.
   Zonder body wordt gewoon genummerd -- er valt dan niets te vergelijken, en stil overslaan is daar gevaarlijker dan een duplicaat.
   AC #12, expliciet: identieke body met afwijkende frontmatter -> schrijven overslaan. De herkomst van de dubbel gaat niet verloren, want bij de sweep-variant blijft het bestaande bestand met zijn eigen source_session staan.
   AC #13 staat in de docstring: dit vangt alleen DEZELFDE slug. Een andere titel of een andere datum (die zit in de slug) glipt er per definitie doorheen.

2. AUTOMATISCHE ONTDUBBELING (AC #7/#8). _maintenance.exact_duplicate_pass(), gedraaid door memory-sweep VOOR supersede_pass. Deterministisch en zonder LLM: bij een identieke body valt er niets te oordelen, en een judge kan daar alleen fout gaan. Werkt ook zonder embedmodel -- juist dan stapelen duplicaten zich op.
   Behouden wordt de oudste op event-tijd; daarna telt of de naam een collision-volgnummer draagt.
   FOUT ONDERWEG, gevonden door de dry run op de echte vault: mijn eerste tie-break sorteerde op pad, en '-' sorteert voor '.', dus '...-resources-2.md' kwam voor '...-resources.md'. Hij hield consequent de DUBBEL in plaats van het origineel. Vastgelegd in test_het_ongenummerde_bestand_blijft_niet_de_kopie.
   Omkeerbaar (AC #8): niets wordt verwijderd, de dubbel krijgt status=superseded plus superseded_by naar de behoudene.

3. superseded_by-NOTATIE. Het onderzoek noteerde 'alle 62 waarden misvormd als [[[x]]]'. Die claim is GETOETST en klopt NIET voor KennisBank zelf: de eigen frontmatter-parser leest [[[slug]]] correct als ['[[slug]]']. Strikte YAML (PyYAML, en daarmee Obsidian) ziet er wel een drievoudig geneste lijst in. Nu met quotes -- ["[[slug]]"] -- waarmee beide lezers op dezelfde waarde uitkomen.

UITGEVOERD OP DE ECHTE VAULT: 17 duplicaatgroepen, 17 bestanden gesloten, 0 groepen over. Alle 17 uit DEZELFDE bronsessie, wat de race-diagnose uit het onderzoek bevestigt. Bestandsaantal onveranderd (1210) -- er is niets verwijderd.

AC #9 -- VOOR/NA RECALL, en de uitkomst weerlegt de aanleiding.

  memory-v2   voor 0.476/0.738 (MRR 0.603)   na 0.476/0.738 (MRR 0.603)
  wiki-v2     voor 0.690/0.966 (MRR 0.813)   na 0.690/0.966 (MRR 0.813)

Exact gelijk. De bewering 'duplicaten schaadden de retrieval' wordt dus NIET gesteund; ze waren neutraal op dit instrument. De reden om ze op te ruimen is correctheid en leesbaarheid, niet gemeten recall.

TUSSENMETING DIE EERST EEN REGRESSIE LEEK: direct na de ontdubbeling gaf memory-v2 @3 0.726 in plaats van 0.738. Oorzaak was geen retrieval-regressie maar de eval-set zelf: entry 63 verwachtte '2026-07-05-interpretatie-van-get-process-cpu-2' -- precies de dubbel die gesloten werd. De overlevende tweeling draagt een BYTE-IDENTIEKE body (geverifieerd), dus de verwachting is even goed vervuld; de entry wees alleen naar de verkeerde helft. Bijgewerkt in de vault-set, met de reden in het why-veld.

EIGEN FOUT DIE DIT VEROORZAAKTE, vermeld omdat hij zich makkelijk herhaalt: mijn vooraf-check op overlap tussen te sluiten bestanden en eval-verwachtingen deed Path(str(expect)).name, terwijl 'expect' een LIJST is. Hij vergeleek dus tegen "['...']" en kon nooit matchen. Correct opnieuw gedaan: 1 van de 176 eval-documenten raakte de ontdubbeling.

AC #1 t/m #6 zijn beantwoord door het onderzoek dat al in deze taak staat (omvang, schrijfpad met file:line, waarom bestaande hulpmiddelen niet grepen, en het criterium 'identieke genormaliseerde body' dat echte duplicaten scheidt van legitiem gesplitste memories).

Tests: 12 nieuwe in test_maintenance (ontdubbelaar), 5 nieuwe in test_memory (collisie-check en notatie). Modules groen: memory 16, maintenance 17, sweep 29, notify 12, reconcile 16, sweeputil 8.
<!-- SECTION:NOTES:END -->
