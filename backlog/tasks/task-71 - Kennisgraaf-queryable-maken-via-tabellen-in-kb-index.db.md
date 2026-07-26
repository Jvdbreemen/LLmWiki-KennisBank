---
id: TASK-71
title: Kennisgraaf queryable maken via tabellen in kb-index.db
status: Done
assignee: []
created_date: '2026-07-25 16:40'
updated_date: '2026-07-26 08:54'
labels:
  - graphify
  - retrieval
  - index
dependencies:
  - TASK-70
modified_files:
  - scripts/_kbindex.py
  - scripts/build-graph-index.py
  - tests/test_graph_index.py
  - scripts/kb-retrieve.py
  - tests/test_kb_retrieve_cold_notice.py
priority: high
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Vraag: kan de graaf bevraagd worden zonder graph.json (4,2 MB) volledig in te lezen?

Ja, en zonder tweede opslag. kb-index.db bestaat al (35 MB, WAL, tabellen meta/docs/vec_docs/fts_docs). Twee tabellen erbij:

  graph_nodes(id TEXT PRIMARY KEY, label, source_file, file_type, community)
  graph_edges(source, target, relation, confidence_score)

met indexen op graph_edges(source), graph_edges(target) en graph_nodes(source_file). Daarmee is 'geef de buren van dit bestand' een indexed lookup in plaats van een JSON-parse van 4,2 MB. Dat past binnen het 2,0s hot-path-budget van kb-retrieve.

BELANGRIJK - geen aparte buurtabel: de buurvraag IS een query op graph_edges. Een voorberekende neighbors-tabel zou een tweede staleness-signaal introduceren zonder guard; dat is exact de faalvorm die TASK-49 documenteerde voor .needs-rebuild.

Vershoud: is_valid_for(conn, embed_id) gate op het embedding-model. Graafversheid is een ONAFHANKELIJKE as. Schrijf de herkomst van de graaf (mtime of hash van graph.json) in de meta-tabel en toets die apart. Een stale graaf naast een verse embedding-index moet degraderen naar 'geen buur', nooit naar 'verkeerde buur' - dezelfde fail-open-discipline die kb-retrieve al heeft.

Builder draait off-path, naast build-kb-index.py, op hetzelfde schema. SCHEMA_VERSION ophogen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 graph_nodes en graph_edges bestaan in kb-index.db met indexen op source, target en source_file
- [x] #2 Builder-script vult ze uit graph.json, draait off-path, en is idempotent
- [x] #3 Herkomst van graph.json (mtime of hash) staat in de meta-tabel en is apart toetsbaar van embed_id
- [x] #4 Een stale of ontbrekende graaf levert 'geen buur' op, nooit een verkeerde buur; fail-open bewezen met een test
- [x] #5 SCHEMA_VERSION opgehoogd; bestaande index wordt correct herbouwd bij versieverschil
- [x] #6 Buurquery gemeten: aantoonbaar sneller dan graph.json parsen, en binnen het hot-path-budget
- [x] #7 Vault-root via _vaultpath.vault_root(); tests in tests/; volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
OPGELEVERD 2026-07-25.

_kbindex.py: ensure_graph_schema, graph_fingerprint, set_graph_fingerprint, graph_is_current, graph_count, replace_graph, graph_neighbors. Tabellen graph_nodes en graph_edges met indexen op source_file, source en target.
scripts/build-graph-index.py: laadt graph.json, idempotent, --force, --json.
tests/test_graph_index.py: 25 tests groen.

Echte graaf geladen: 3956 nodes, 6860 edges. Tweede run herkent de vingerafdruk en doet niets.

TWEE ONTWERPKEUZES onderweg:
1. ensure_graph_schema maakt OOK de meta-tabel. De graafbouwer kan draaien voordat de embedding-index bestaat (verse vault, of een machine zonder embedmodel); meta alleen in ensure_schema aanmaken zou die volgorde stilzwijgend verplicht maken. Kwam als testfout naar boven ('no such table: meta').
2. De vingerafdruk wordt PAS na een geslaagde vervanging weggeschreven. Bij een crash halverwege blijft de oude afdruk staan, zodat de volgende run opnieuw laadt in plaats van een halve graaf als actueel te beschouwen.

SNELHEID GEMETEN (AC #6): buurquery 0,09 ms gemiddeld over 20 runs, tegen 68,98 ms om graph.json (4,2 MB) te parsen. 809x sneller, 0,004% van het 2,0s hot-path-budget. Ruim binnen wat kb-retrieve kan dragen.

DE VOORSPELLING IS GEFALSIFIEERD - en dat is de belangrijkste uitkomst van deze taak.

Hypothese was: bij twee gemeten faalgevallen stonden broertjes uit dezelfde sessie WEL in de top-5 terwijl het gezochte document ontbrak, dus een same_session-graafbuur zou die gevallen moeten oplossen. Getoetst op de echte graaf: in geen van beide gevallen levert de buurquery het gezochte document op.

Oorzaak, gemeten en niet geraden:

1. DE SESSIE IS TE GROOT. 2026-06-28-llmwiki-kennisbank-57fcd6ff.jsonl bevat 148 memories. De ster-topologie uit TASK-70 verbindt die allemaal met EEN hub. Gevolg: een stap vanaf een willekeurig lid levert alleen de hub (steeds dezelfde), twee stappen leveren alle 148 leden met gewicht 1,00 - ononderscheidbaar. 'Uit dezelfde sessie' is geen betekenisvol verband bij die omvang.

2. DE CONCEPT-EDGE BESTAAT NIET. Tussen 09-memory/2026-07-02-status-sqlite-vec.md en -gebruik-van-sqlite-vec.md loopt GEEN enkele edge, behalve via de sessie-hub. De LLM-extractie heeft ze nooit verbonden omdat ze in verschillende chunks van 75 bestanden zaten - exact de structurele beperking uit TASK-70, nu zichtbaar in zijn gevolg.

Edgeverdeling: contains 3396, references 1259, same_session 1025, conceptually_related_to 461, shares_tag 356, rationale_for 170, semantically_similar_to 90, shares_data_with 43, implements 34, cites 25, calls 1.

Zonder same_session blijven er per bestand 0-2 buren over, en die wijzen naar andere documenten die het antwoord evenmin dragen.

CONSEQUENTIE: _rank NIET bedraden met de graafbuur, nog niet.

De infrastructuur is klaar en snel, maar de buur zou vandaag niets meetbaars toevoegen aan de recall en kan wel correcte treffers verdringen. Bedraden zonder aantoonbaar effect is precies het soort verbetering-op-gevoel dat de eval-set moest voorkomen.

De bottleneck is EDGEKWALITEIT, niet querysnelheid. Wat eerst moet:
- same_session bruikbaar maken: nu is het een sessie-brede ster over 148 memories. Kandidaten: beperken tot memories die binnen N minuten van elkaar zijn aangemaakt, of tot naburige posities in de sessievolgorde. Dan wordt het weer een affiniteitssignaal in plaats van een lidmaatschapslabel.
- de chunkgrens doorbreken: concept-edges lopen nooit tussen chunks. Een tweede extractiepas die ALLEEN naar bestaande node-labels kijkt (goedkoop, geen volledige tekst) zou cross-chunk verbanden kunnen leggen.

Pas als een van beide meetbaar buren oplevert die het gezochte document bevatten, is bedraden in _rank te verdedigen. De v2-meetsets (memory@5 = 0.738, 22 geverifieerde faalgevallen) staan klaar om dat te toetsen.

AFGEROND 2026-07-26. Gemerged als PR #63.

AC #7 geverifieerd: build-graph-index.py haalt de vault-root via `from _vaultpath import vault_root`, geen hardcoded default (ADR-0002). Tests in tests/test_graph_index.py (inmiddels 28). Suite groen: 869 tests.

NAWERK, belangrijk voor wie deze taak later leest: de opslagkeuze uit AC #1 (tabellen IN kb-index.db) is in TASK-75 teruggedraaid. Dat bestand wordt door build-kb-index.py ge-unlinkt bij een herbouw, en nam de graaf mee. De tabellen wonen nu in een eigen kb-graph.db; de API (graph_neighbors, graph_is_current) is ongewijzigd, alleen de verbinding komt uit graph_connect(). AC #1 blijft afgevinkt omdat het toen klopte en de functionaliteit geleverd is -- maar de tekst beschrijft niet meer de huidige staat.
<!-- SECTION:NOTES:END -->
