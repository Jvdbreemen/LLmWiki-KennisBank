---
id: TASK-70
title: 'Deterministische edge-laag: documentnodes en herkomst-edges in de kennisgraaf'
status: In Progress
assignee: []
created_date: '2026-07-25 16:29'
updated_date: '2026-07-25 16:35'
labels:
  - graphify
  - retrieval
  - graaf
dependencies:
  - TASK-67
modified_files:
  - scripts/graph-link-layer.py
  - tests/test_graph_link_layer.py
priority: high
ordinal: 80000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Volgt op TASK-67. Na de scope-verbreding telt de graaf 2651 nodes maar 437 geisoleerde nodes, 675 componenten en een gemiddelde graad van 1,78. De grootste component (1219) is de oude wiki-graaf; de geheugenlaag en 03-projecten vormen eilanden.

Oorzaak is structureel: LLM-extractie gebeurt per chunk, en een subagent kan alleen edges leggen tussen bestanden die hij zelf ziet. Met 75 memories per chunk is een edge tussen memory #3 en memory #900, of tussen een memory en een wiki-artikel, principieel onmogelijk. Grotere chunks schalen niet (dan moet 1185 bestanden in een context).

OPLOSSING: een deterministische laag bovenop de extractie, zonder LLM.

1. Documentnode per bronbestand: `doc:<vault-relatief-pad>`, met `contains`-edges naar de concept-nodes uit dat bestand. Hiermee verdwijnt isolatie per constructie: elke concept-node hangt aan zijn document.
2. Doc-doc-edges uit structuur die al in de vault zit:
   - `source_session` in memory-frontmatter: memories uit dezelfde sessie, en de wiki-artikelen/raw-sessies met dezelfde herkomst;
   - `[[wikilinks]]` in de tekst van memories en artikelen;
   - gedeelde tags.

De 75x75-variant (alle concepten van bestand A aan alle van B) is bewust verworpen: kwadratische explosie zonder informatiewinst.

RISICO dat gemeten moet worden, niet aangenomen: ~2650 `contains`-edges verdubbelen de gemiddelde graad en laten Leiden hercluteren. Als de bestaande wiki-communities daardoor uiteenvallen in per-document-clusters, is de graaf een bestandsbrowser geworden in plaats van een kennisgraaf. Dat is een regressie, ook al verbetert het isolatiecijfer. Voor- en nameting van componenten, graad EN communitystructuur is onderdeel van de taak.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Script bouwt documentnodes met contains-edges naar de concept-nodes van hetzelfde bronbestand; geen enkele LLM-aanroep
- [x] #2 Doc-doc-edges gelegd uit source_session, [[wikilinks]] en gedeelde tags, elk met een eigen relatie-naam zodat de herkomst van een edge herleidbaar blijft
- [x] #3 Geisoleerde nodes teruggebracht tot vrijwel nul; voor- en nameting van componenten en gemiddelde graad vastgelegd
- [x] #4 Communitystructuur voor en na vergeleken; expliciet oordeel of de wiki-communities intact blijven of uiteenvallen in per-document-clusters
- [x] #5 graph.json geback-upt voor het schrijven, zodat de oude topologie vergelijkbaar blijft
- [x] #6 Idempotent: een tweede run voegt niets toe
- [ ] #7 Vault-root via _vaultpath.vault_root(); tests in tests/; volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
RESULTAAT 2026-07-25. scripts/graph-link-layer.py toegevoegd (+ tests/test_graph_link_layer.py, 8 tests groen), gedeployed naar $VAULT/.claude/scripts.

Toegevoegd aan de graaf: 1305 documentnodes en 4494 edges, nul LLM-tokens.
  contains      2623
  same_session  1025
  references     490
  shares_tag     356
  2 tags overgeslagen omdat ze > 25 documenten dekken (categorie, geen verband)

Topologie voor -> na (backup in graphify-out/graph.pre-linklayer.json):
  nodes            2651 -> 3956
  edges            2366 -> 6763
  geisoleerde nodes 437 -> 2
  componenten       675 -> 29
  grootste component 1219 -> 3545
  gemiddelde graad 1,78 -> 3,42

Idempotentie geverifieerd op de echte graaf: tweede run voegt 0 nodes en 0 edges toe.

COMMUNITY-REGRESSIETOETS (AC #4): geen bestandsbrowser geworden, integendeel.

  communities                        775 -> 378
  communities met <= 2 nodes         547 -> 88
  communities die MEERDERE bronbestanden overspannen   35% -> 63%
  idem, alleen communities >= 5 nodes                  58% -> 77%
  grootste communities        [56,46,35,34,...] -> [75,60,60,58,51,...]

De vrees was dat contains-edges elke community zouden laten samenvallen met een
bestand. Het omgekeerde gebeurt: het aandeel communities dat meerdere bestanden
omvat stijgt van 35% naar 63%. De documentnode werkt als brug tussen concepten
uit verschillende bestanden in plaats van als muur eromheen.

RESTEREND GAT, eerlijk vastgelegd: communities die zowel 02-wiki als 09-memory
bevatten: 1 voor, 1 na. De wiki- en geheugenlaag zitten nu wel in EEN component
(3545 nodes) maar Leiden scheidt ze nog steeds. Oorzaak: same_session verbindt
memories onderling, maar wiki-artikelen dragen hun herkomst als
[[raw-sessie-...]]-wikilink en niet als source_session-frontmatter, dus er is
geen sleutel die de twee lagen koppelt. Een vervolgstap zou die twee
herkomstvormen op elkaar moeten afbeelden (sessie-id <-> raw-sessie-artikel).

ANTWOORD op 'kan kb-recall de graaf lezen?': ja, maar de meetbare winst is nu een enkele vraag.

Ontwerp dat past bij de hot-path-eis (2,0s embed-budget, fail-open): NIET graph.json inlezen per prompt (1,8 MB), maar off-path een buurtabel afleiden en die in kb-index.db zetten - dezelfde plek en hetzelfde geldigheidscontract als de rest van de index (_kbindex.is_valid_for). Een los neighbors.json zou een eigen staleness-probleem krijgen zonder guard; dat is precies de faalvorm die TASK-49 documenteerde voor .needs-rebuild.

Hoeveel valt er te winnen? _rank.one_hop_neighbor voegt EEN buur toe, met score 0.0 en neighbor=True, dus onderaan de lijst. Die kan alleen recall@5 bewegen, en alleen als het verwachte artikel nog niet in de top 5 stond. Wiki staat op @5 = 1.000: nul ruimte. Memory op @5 = 0.941, oftewel 1 van de 17 vragen mist.

Die ene vraag is: 'Wat is de prioriteitsvolgorde van de gefaseerde data-inname strategie?' (type beslissing), verwacht 09-memory/2026-06-27-gefaseerde-data-inname-strategie.md. Dat bestand bestaat, maar embedding-recall vindt het niet (rank 0).

BELANGRIJK: de huidige one_hop_neighbor KAN die vraag niet redden. Hij slaat niet-wiki-hits over en accepteert alleen targets die als artikel in 02-wiki/ bestaan - een memory kan er per definitie niet uitkomen. Een graaf-buur voor de geheugenlaag bestaat vandaag helemaal niet.

Conclusie: de edge-laag is gerechtvaardigd door /brug, /graphify query, auto-crosslink en navigeerbaarheid - niet door recall@k. AC #6 van TASK-67 hoort daarop herschreven te worden.
<!-- SECTION:NOTES:END -->
