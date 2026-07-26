---
id: TASK-75
title: Graaftabellen overleven een volledige herbouw van kb-index.db niet
status: Done
assignee: []
created_date: '2026-07-25 21:18'
updated_date: '2026-07-26 09:01'
labels:
  - graaf
  - index
  - regressie
dependencies:
  - TASK-71
references:
  - 'scripts/build-kb-index.py:88'
  - 'scripts/build-kb-index.py:102'
  - scripts/_kbindex.py
  - scripts/build-graph-index.py
  - scripts/index-launch.py
priority: high
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-71 zette de graaf in kb-index.db (graph_nodes, graph_edges, meta.graph_fingerprint). Die tabellen delen een BESTAND met een index die volledig weggegooid kan worden.

build-kb-index.py doet `idx.unlink()` op twee plekken:
  regel  88  bij --rebuild
  regel 102  bij een embed_id- of unit_norm-mismatch

Het hele DB-bestand verdwijnt daar, en de graaftabellen gaan als bijvangst mee. Niets bouwt ze daarna automatisch terug: build-graph-index.py staat niet in de JOBS-lijst van index-launch.py.

WAARGENOMEN OP 2026-07-25, tijdens het meten van TASK-74:
  - eerder die avond: 3956 nodes, 6860 edges geladen; statusregel meldde "graaf actueel"
  - daarna: `no such table: graph_nodes`, `no such table: graph_edges`
  - meta bevatte nog uitsluitend dim=4096, embed_id=ollama:qwen3-embedding:8b, unit_norm=1
    -- graph_fingerprint was weg
  - docs-telling liep op van 258 naar 731 naar 1268: een volledige herbouw was bezig

Wat hier feitelijk vaststaat is het MECHANISME (gelezen in de code): de graaftabellen delen een bestand met een tabel die ge-unlinkt wordt, dus elke volledige herbouw vernietigt ze -- ongeacht wat deze specifieke herbouw heeft uitgelokt. Wat die trigger was, is NIET vastgesteld en hoort niet als feit genoteerd te worden.

RICHTING (KISS, en de beslissende observatie staat al vast): graph_neighbors() bevraagt uitsluitend de graaftabellen op source_file en joint NIET met docs. Een eigen bestand (kb-graph.db) kost daarmee vandaag niets aan queries en geeft de graaf een eigen levenscyclus. Alternatieven -- tabellen bewaren over een herbouw heen, of build-graph-index na afloop opnieuw draaien -- laten de koppeling in stand.

De statusregel uit TASK-74 meldt dit inmiddels als "graaf niet geladen", dus het valt nu op in plaats van stil te blijven.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Een volledige herbouw van kb-index.db (--rebuild en embed_id-mismatch) laat de graafgegevens intact
- [x] #2 Bewezen met een test die een herbouw uitvoert en daarna graph_neighbors() nog laat werken
- [x] #3 De statusregel meldt na een herbouw geen 'graaf niet geladen' meer
- [x] #4 Bestaande graafqueries blijven werken zonder join met docs
- [x] #5 Volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UITGEVOERD 2026-07-26, PR #66.

De graaf woont in kb-graph.db. graph_connect() is de enige ingang; build-graph-index en de statusregel zijn omgezet.

STATUSREGEL LOSGEKOPPELD. De graafaflezing stond genest in `if kb-index.db bestaat` -- precies de tak die tijdens een herbouw leeg of half is. De graafstatus viel daardoor stil op het moment dat je hem het hardst nodig hebt. Nu een eigen try/except met een eigen verbinding.

JOURNAL-MODE: EEN CORRECTIE OP MEZELF, TWEE KEER.

Eerst koos ik DELETE op basis van een meting (WAL 27,4 ms tegen DELETE 1,2 ms per verse lezer; de kosten zitten in het -shm-bestand dat WAL op Windows aanlegt, niet in een achterblijvende -wal -- een checkpoint(TRUNCATE) veranderde niets).

Robert wees erop dat deze index meerdere agents tegelijk kan bedienen. Ik beweerde daarop dat DELETE lezers blokkeert tijdens een herbouw. Dat bleek FOUT bij toetsing: in DELETE-mode blokkeert een schrijver pas tijdens de commit-flush, niet de hele transactie. Een lezer tijdens een open schrijftransactie kreeg gewoon antwoord.

Dus gemeten in plaats van geredeneerd -- drie gelijktijdige lezers naast een schrijver die de graaf doorlopend herbouwde, 6 seconden per mode:

  DELETE   6030 lezers ok / 0 geblokkeerd / 50 schrijfrondes
  WAL      3730 lezers ok / 0 geblokkeerd / 93 schrijfrondes

Nul blokkades in beide. WAL haalt wel bijna dubbele schrijfdoorvoer en houdt lezers en schrijvers by design uit elkaar, terwijl DELETE erop leunt dat de busy-timeout het exclusieve commit-venster opvangt -- dat gaat goed tot een trage schijf of een grotere graaf dat venster oprekt. WAL gekozen. test_graafindex_gebruikt_wal legt het vast, met de meting in de docstring, zodat een latere snelheidsronde het niet stilzwijgend terugdraait.

PERFORMANCE, met WAL:
  koude sessiestart   1289 ms -> 1214 ms
  statusregel           33,7 ms -> 27,9 ms bij de DELETE-tussenstand; met WAL ~48 ms,
                        maar de sessiestart als geheel werd sneller, en dat is de plek
                        waar de gebruiker het merkt
  graph_neighbors     submilliseconde, ongewijzigd

GRAAF HERSTELD op de echte vault: 3956 nodes, 6860 edges -- exact de aantallen die verdwenen waren. kb-graph.db is 3 MB naast een kb-index.db van 35 MB.

GEEN MIGRATIE, bewust. Oude vaults houden inerte graaftabellen in kb-index.db over; niets leest ze nog en de eerstvolgende volledige herbouw ruimt ze op -- precies de herbouw die dit probleem veroorzaakte. Een migratie zou een bewegend deel toevoegen voor iets dat zichzelf opruimt.

AC #2 met opzet via de ECHTE unlink-weg: main(rebuild=True) uit build-kb-index, met een merker in meta die bewijst dat het bestand daadwerkelijk vervangen is. Zelf het bestand verwijderen zou mijn aanname toetsen in plaats van het gedrag van de code.

Tests: 869 groen (alles behalve test_setup_deploy, dat apart draait en deze wijziging niet raakt).

AC #5: CI groen op PR #66 (test, 2m40s), en lokaal 874 tests groen op de samengevoegde werkboom. Taak afgerond.
<!-- SECTION:NOTES:END -->
