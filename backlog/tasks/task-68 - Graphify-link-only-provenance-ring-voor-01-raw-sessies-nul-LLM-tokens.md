---
id: TASK-68
title: 'Graphify: link-only provenance-ring voor 01-raw/sessies (nul LLM-tokens)'
status: Done
assignee: []
created_date: '2026-07-25 15:21'
updated_date: '2026-07-26 10:14'
labels:
  - graphify
  - provenance
  - retrieval
dependencies: []
priority: medium
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Doel: sessies en transcripts vindbaar maken in de graaf zonder ze semantisch te extraheren.

01-raw/sessies telt 834 bestanden / 1,41M woorden (~2,2M input-tokens). LLM-extractie daarvan levert vooral concept-nodes die echo's zijn van de 02-wiki-artikelen die eruit gedestilleerd zijn: near-duplicate buren die de graafbuur-signaalwaarde in _rank.py verwateren. Vindbaarheid is het doel, niet extractie.

Deze bestanden hebben gestructureerde frontmatter (type: raw-sessie, source, source_id, source_path, date, project_path, tags). Daaruit is één leaf-node per sessie te bouwen, met edges naar wiki- en memory-nodes via source_session / Sessie-herkomst en bestaande wikilinks. Kosten: nul tokens, geen extern verkeer.

Levert de queries "welk transcript zit achter dit artikel" en "in welke sessie deed ik X" als graaf-traversal, in plaats van als full-text zoekactie.

Scriptconventie: vault-root uitsluitend via _vaultpath.vault_root() (ADR-0002). Nooit een hardcoded pad.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Script genereert leaf-nodes uit frontmatter van 01-raw/sessies zonder enige LLM-aanroep
- [x] #2 Edges gelegd via source_session / Sessie-herkomst naar bestaande wiki- en memory-nodes; niet-matchende sessies worden geteld en gerapporteerd, niet stil weggelaten
- [x] #3 Nodes zijn herkenbaar als provenance (eigen node-type of confidence-markering), zodat ranking ze kan onderscheiden van kennis-nodes
- [x] #4 _rank.py one_hop_neighbor promoveert provenance-nodes nooit boven directe hits
- [x] #5 Vault-root via _vaultpath.vault_root(); geen hardcoded pad
- [x] #6 recall@k met kb-eval.py niet slechter dan zonder de ring
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UITGEVOERD 2026-07-26. scripts/graph-provenance-ring.py + tests/test_graph_provenance_ring.py (14 tests).

TWEE KOPPELWEGEN, allebei uit velden die er al staan, nul LLM-aanroepen:
  source_session (memory-frontmatter) == basename(source_path) (sessie-frontmatter)
  [[raw-sessie-...]]-wikilinks, zoals wiki-artikelen ze onder Sessie-herkomst zetten

Bewust via source_path en niet via het parsen van bestandsnamen: het veld staat er, en een parser op naamconventies breekt zodra iemand een sessie hernoemt. _basename() normaliseert eerst backslashes -- source_path is opgeslagen zoals de importeur hem zag, en Path() ziet die op POSIX niet als scheidingsteken.

BELANGRIJKE ONTWERPKEUZE, gemaakt NA de eerste dry run op de echte vault.

De eerste versie gaf elke sessie een node: 772 nodes, waarvan 724 zonder enige verwijzing. Dat is geen ring maar ruis, en het zou de isolatie-winst van TASK-70 (437 -> 2 geisoleerde nodes) in een klap ongedaan maken. Nu worden standaard alleen sessies opgenomen waar daadwerkelijk naar verwezen wordt. De rest verdwijnt NIET stilzwijgend: geteld in het rapport, met voorbeelden bij naam, want '724 ongekoppeld' is een getal waar niemand iets mee doet. Wie ze toch wil: --include-unreferenced.

RESULTAAT OP DE ECHTE VAULT: 48 sessie-nodes, 782 edges (769 via source_session, 13 via wikilink). Van 772 sessies wordt er naar 48 verwezen.

GRAFIEKGEZONDHEID, voor -> na:
  nodes        3956 -> 4004
  edges        6860 -> 7642
  geisoleerd      2 -> 2      (ongewijzigd)
  componenten    29 -> 27     (beter)
  gem. graad   3,42 -> 3,77   (beter)

De ring maakt de graaf dus samenhangender in plaats van rommeliger -- precies wat de keuze hierboven moest bewerkstelligen.

AC #3: nodes dragen file_type 'provenance' en een eigen id-prefix 'sessie:'.

AC #4 is een STRUCTURELE eigenschap, geen weging: _rank.one_hop_neighbor accepteert alleen targets die als artikel in 02-wiki/ bestaan, dus een sessie in 01-raw kan er per constructie niet uitkomen. Vastgelegd in RankIsolatieTest, die omvalt zodra iemand die filter verruimt.

AC #6: recall@1 en @3 IDENTIEK voor en na (wiki-v2 0.690/0.966, memory-v2 0.476/0.738). MRR memory 0.603 -> 0.601; dat is een verschuiving binnen de top-5 van een enkele vraag, geen recall-verschil.

BLAD, GEEN KNOOPPUNT: geen edges tussen sessies onderling. Dat zou een tweede hub-structuur opleveren naast de same_session-ster, en die bleek in TASK-71 al te grof om als buursignaal te dienen.

Suite: 888 tests groen (alles behalve test_setup_deploy).
<!-- SECTION:NOTES:END -->
