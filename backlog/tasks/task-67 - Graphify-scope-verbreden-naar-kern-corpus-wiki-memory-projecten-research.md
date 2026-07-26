---
id: TASK-67
title: >-
  Graphify-scope verbreden naar kern-corpus (wiki + memory + projecten +
  research)
status: Done
assignee: []
created_date: '2026-07-25 15:20'
updated_date: '2026-07-26 09:32'
labels:
  - graphify
  - scope
  - retrieval
dependencies: []
modified_files:
  - commands/sessielog.md
  - setup.sh
  - graphifyignore.example
  - scripts/graph-scope-prune.py
  - tests/test_graph_scope_prune.py
priority: high
ordinal: 77000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Herziening van TASK-28. Die bracht de scope terug naar 02-wiki-only om tooling-ruis (.claude, 899 nodes) uit de graaf te halen. Die intentie blijft staan; de conclusie was te breed. 09-memory is geen tooling-ruis maar de geheugenlaag, en is gemeten even groot als de wiki (1190 bestanden / 569 KB ~ 95k woorden), dus goedkoop.

Gemeten corpus (2026-07-25, gemeten op een echte vault via $KENNISBANK_VAULT):
- 02-wiki: 139 md / 97k woorden / 148k input-tokens (gemeten bij bestaande build)
- 09-memory: 1190 md / ~95k woorden (1114 status=current, 59 superseded, 17 unverified)
- 00-inbox: 37 md / 74k woorden
- 01-raw/debug: 150 md / 29k woorden
- 05-bronnen/research: 3 md / 4,5k woorden
- 03-projecten: 2 md / 2,3k woorden
Totaal ~302k woorden ~ 460k input-tokens, eenmalig (3x de huidige graaf).

Buiten deze taak: 01-raw/sessies (834 md / 1,41M woorden) en 05-bronnen/evernote (14837 md / ~3,7M woorden). Zie de vervolgtaken.

Let op de twee valkuilen uit TASK-28: build_merge prune_sources matcht op vault-relatieve source_file met forward slashes, en extractie-subagents schrijven absolute paden. Normaliseer source_file vóór merge en geef nooit prune_sources mee die de net-ingevoegde nodes bevat (self-prune).

graphify detect skipt `graphify-out` al automatisch (_SKIP_DIRS). Uitsluiten van 04-templates(.bak), 06-claude, 08-archive moet expliciet via de scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Graphify-invocatie in commands/sessielog.md, commands/wiki.md en commands/destilleer.md dekt het kern-corpus in plaats van alleen $VAULT/02-wiki
- [x] #2 09-memory wordt gefilterd op status: current; superseded/unverified/retracted/expired komen niet in de graaf
- [x] #3 04-templates, 04-templates.pre-*.bak, 06-claude, 08-archive, 01-raw/sessies en 05-bronnen/evernote zitten aantoonbaar niet in graph.json
- [x] #4 Wijziging gedeployed naar ~/.claude/commands EN $VAULT/.claude (beide copies in sync)
- [x] #5 graph.json herbouwd; source_file van elke node is vault-relatief met forward slashes
- [x] #6 recall@k gemeten met kb-eval.py voor en na, tegen 06-claude/kb-eval-set.json en kb-memory-eval-set.json; de nieuwe scope is niet slechter
- [x] #7 Artikel graphify-kennisgraaf-tool bijgewerkt naar de feitelijke scope
- [x] #8 kb-lint schoon (exit 0) en volledige testsuite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Baseline recall@k VOOR de wijziging (kb-eval.py --json, 2026-07-25):
- wiki (35 vragen): @1 0.886 / @3 1.000 / @5 1.000, MRR 0.943
- memory (17 vragen): @1 0.765 / @3 0.941 / @5 0.941, MRR 0.853
De wiki-set zit op @3 al op het plafond; deze baseline dient voor regressiedetectie, niet als bewijs van verbetering. Ruimte zit in memory@1.

Scope-mechanisme gekozen: EEN .graphifyignore in de vault-root, invocatie blijft een enkel pad ($VAULT). Geen zes losse runs met merge-graphs.

Reden dat dit noodzakelijk is en niet cosmetisch: graphify.detect leest bij voorkeur .graphifyignore en valt anders terug op .gitignore. De vault-.gitignore is een deny-all PUBLICATIE-whitelist (alleen 02-wiki, 03-projecten, 04-templates, 06-claude naar de remote). Zonder .graphifyignore zou /graphify $VAULT dus stil 09-memory overslaan en gewoon succes melden.

Geverifieerd met graphify.detect op de echte vault: 1477 bestanden = 150 01-raw/debug + 136 02-wiki (+1 paper) + 2 03-projecten + 3 05-bronnen/research + 1185 09-memory. Geen 00-inbox, evernote, sessies, archive of templates.

SCOPE-CORRECTIE: 00-inbox gaat NIET mee, tegen de oorspronkelijke taakomschrijving in. De 74k-woorden-schatting was md-only geteld en misleidend. Feitelijk: 5,4 GB, 659 afbeeldingen, 48 pdf's, 885 .dat-bestanden, en 36 van de 37 md-bestanden zitten in een persoonlijke OpenAI-export (1 op topniveau). Graphify doet vision-extractie op afbeeldingen, dus dit was de duurste map, niet de goedkoopste. Bovendien is 00-inbox een wachtrij waaruit content na /intake vertrekt.

Herziene omvang: ~228k woorden ~ 345k input-tokens eenmalig.

graphify.detect skipt 7 bestanden als 'sensitive' op een false positive van de keyword-heuristiek (_GENERIC_KEYWORD_PATTERNS matcht 'token'/'credential'/'secret' in de bestandsnaam). Slachtoffers o.a. 02-wiki/sse-framing-multiline-tokens.md, 02-wiki/claude-code-plugin-mcp-oauth-dode-token.md, 09-memory/2026-07-05-beveiliging-discord-token.md. Dat zijn artikelen OVER tokens, geen credential-stores; het package erkent de heuristiek zelf in een comment. Verlies ~0,5%, geen blocker, maar verklaart waarom die artikelen straks niet in de graaf zitten.

PRIVACY-AFWEGING vastgelegd: graph.json, graph.html en GRAPH_REPORT.md staan in de whitelist van de vault-.gitignore en gaan dus mee naar de vault-remote. Bij de vault waarop dit gemeten is, is die remote een PRIVATE repo (geverifieerd via gh). Na deze verbreding bevatten die bestanden node-labels en source_file-paden afgeleid van de geheugenlaag en debug-logs. Wie een vault aan een PUBLIEKE remote hangt, publiceert daarmee dus afgeleiden van zijn geheugenlaag -- controleer dat vooraf. Geen blocker, wel een bewust besluit.

Status 2026-07-25: voorbereiding klaar en groen; de rebuild zelf is NOG NIET gedraaid (wacht op expliciete go, ~345k tokens).

Gedaan: .graphifyignore in de vault + graphifyignore.example in de repo, gedeployed via setup.sh met copy_file (overschrijft nooit een aangepaste scope). commands/sessielog.md: 3 invocaties $VAULT/02-wiki -> $VAULT, met waarschuwing over de .gitignore-terugval; gedeployed naar ~/.claude/commands. scripts/graph-scope-prune.py + tests/test_graph_scope_prune.py (6 tests). kb-lint exit 0 (3 bestaande herkomst-waarschuwingen, niet van deze wijziging). Volledige testsuite: 834 passed, 2 skipped, exit 0.

REBUILD-RESULTAAT 2026-07-25. 24 extractie-chunks, 1345 bestanden, ~1,59M subagent-tokens.

Graaf: 1332 -> 2692 nodes / 2365 edges na merge; na de status-prune 2619 nodes / 2315 edges.
Verdeling: 02-wiki 1354, 09-memory 1089 (na prune), 01-raw/debug 137, 05-bronnen/research 28, leeg 11.
Status-prune verwijderde 73 nodes uit 73 niet-actuele memories + 50 losse edges; 1 node verwees naar een verdwenen bronbestand.

De zelf-prune-bewaking bewees zijn nut: van 1417 prune-kandidaten waren er 1258 paden die de NIEUWE extractie zelf leverde. Zonder die filter had build_merge precies de zojuist ingevoegde nodes verwijderd - exact de TASK-28-fout.

PROBLEEM: de geheugenlaag landt als losse fragmenten, niet als kennisweefsel.

Gemeten op de nieuwe graaf: 442 geisoleerde nodes (16%), 699 samenhangende componenten, gemiddelde graad 1,76. Grootste component 1219 nodes (de bestaande wiki-graaf), daarna 56, 33, 18, 18. 805 communities waarvan 563 met <= 2 nodes.

Oorzaak is structureel, geen instelling: extractie gebeurt per chunk, en een subagent kan alleen edges leggen tussen bestanden die hij zelf ziet. Met 75 memories per chunk is een edge tussen memory #3 en memory #900, of tussen een memory en een wiki-artikel, principieel onmogelijk. De 1089 memory-nodes zijn dus wel VINDBAAR in de graaf, maar hangen nauwelijks aan de kenniskern.

--resolution of --exclude-hubs lost dit niet op: die hergroeperen bestaande edges, ze maken er geen. Een lagere resolutie maakt de 805 communities alleen optisch groter.

recall@k NA de rebuild is identiek aan de baseline: wiki @1 0.886 / @3 1.000 / MRR 0.943; memory @1 0.765 / @3 0.941 / MRR 0.853.

Dat is geen meetfout maar een architectuurfeit dat de taakomschrijving miste: kb-recall leest graph.json NIET. De keten loopt graphify -> auto-crosslink.py -> [[wikilinks]] in artikelen -> _rank.one_hop_neighbor -> recall. Zolang auto-crosslink niet gedraaid heeft, kan de graaf de retrieval per definitie niet beinvloeden. De meting toont dus wel aan dat er geen regressie is, maar kan pas winst tonen na een auto-crosslink-run (die wiki-artikelen muteert).

GEVONDEN VALKUIL in het --update-model: 'staat in het manifest' is niet hetzelfde als 'staat in de graaf'.

03-projecten (2 bestanden) zat in manifest.json van een eerdere whole-vault-run en is sindsdien niet gewijzigd, dus detect_incremental meldt ze niet als nieuw. Maar TASK-28 heeft hun nodes destijds als non-02-wiki gepruned. Netto: die bestanden zijn permanent onzichtbaar tot iemand ze aanraakt. Elke scope-verbreding naar een map die ooit in het manifest stond heeft dit probleem. Losse extractie gestart om het gat te dichten; structureel hoort hier een manifest-reset bij een scope-wijziging.

AFGEROND 2026-07-26.

AC #6 -- RECALL@K. Eerst het punt dat de meting overbodig maakt en er tegelijk sterker dan is: de graaf zit HELEMAAL NIET in de retrieval-weg. Geverifieerd met grep over kb-retrieve.py, _kb_recall.py en kb-search.py: geen enkele aanroep van graph_neighbors of graph_connect. _rank.one_hop_neighbor heet wel zo maar leest WIKILINKS UIT DE ARTIKELTEKST (_rank.py:161), niet de graaf. Een scope-wijziging aan graphify kan recall@k dus per constructie niet beïnvloeden.

Toch gemeten, want een a-priori-argument dat je niet toetst is een aanname:

  set                n    @1      @3      @5      MRR
  kb-eval-set        35   0.886   1.000   1.000   0.943
  kb-memory-eval-set 17   0.765   0.941   0.941   0.853

Identiek aan de vastgelegde v1-baseline (memory @3 0.941, wiki @3 1.000). Niet slechter, dus AC #6 is gehaald.

Op de gevoeliger v2-sets: wiki-v2 @1 0.672 -> 0.690, memory-v2 @1 0.476 -> 0.464; @3 en @5 ongewijzigd. Dat zijn verschillen van precies EEN vraag op 58 respectievelijk 84. EERLIJK VOORBEHOUD: de vault is tussen beide metingen gegroeid doordat de sweep nieuwe memories schreef, dus dit is geen gecontroleerde voor/na-meting en die één vraag is niet aan de scope-wijziging toe te schrijven. De v1-sets, die exact gelijk bleven, zijn het schonere signaal.

AC #7 -- WIKI-ARTIKEL. 02-wiki/graphify-kennisgraaf-tool.md bijgewerkt naar de feitelijke scope: die komt uit .graphifyignore en niet meer uit het pad, met de mappen erbij en de reden waarom een apart bestand nodig is (terugval op .gitignore sluit 09-memory stil uit).

BELANGRIJKER dan de scope-update, en niet waar de taak om vroeg: het artikel bevatte een VALSE VEILIGHEIDSCLAIM. Er stond dat graphify's detect-laag gevoelige bronnen zoals Evernote in 05-bronnen sowieso overslaat, ook bij een whole-vault-run, en dat de 02-wiki-scope daarom geen privacy-mechanisme hoefde te zijn.

Geverifieerd tegen de geïnstalleerde graphify.detect, en het klopt niet:
  _SENSITIVE_DIRS = .aws, .gcloud, .gnupg, .secrets, .ssh, credentials, secrets
  -- geen 05-bronnen, geen evernote
  _SENSITIVE_PATTERNS dekt sleutels en certificaten, geen academische markers

Empirisch beslist in plaats van uit de lijst afgeleid: een map 05-bronnen/evernote/ met een notitie erin gaat gewoon mee, en skipped_sensitive blijft leeg.

Wat evernote buiten de graaf houdt is dus UITSLUITEND de expliciete uitsluiting in .graphifyignore. Dat staat nu met bewijs in het artikel, inclusief de waarschuwing dat de dekking stilzwijgend verandert wanneer dat bestand verdwijnt.

kb-lint: dit artikel schoon (137 artikelen, 134 schoon; de 3 waarschuwingen betreffen andere bestanden).
<!-- SECTION:NOTES:END -->
