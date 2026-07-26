---
id: TASK-72
title: Eval-sets uitbreiden met waargenomen-rang als selectiecriterium
status: In Progress
assignee: []
created_date: '2026-07-25 16:41'
updated_date: '2026-07-25 18:19'
labels:
  - retrieval
  - eval
  - meting
dependencies: []
modified_files:
  - (vault) 06-claude/kb-memory-eval-set-v2.json
  - (vault) 06-claude/kb-eval-set-v2.json
  - (vault) 06-claude/README-eval-sets.md
priority: high
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Doel: een meetinstrument dat kan aantonen of een graaf-buur de retrieval verbetert. De huidige sets zijn te klein en te verzadigd: wiki @3 = 1.000 (geen ruimte), memory 17 vragen waarvan er 1 mist.

METHODE, en de val die vermeden moet worden. Je kunt niet 10 vragen verzinnen die falen en dat een meting noemen. Vragen falen om twee heel verschillende redenen:
  (a) het verwachte document bestaat en is inhoudelijk vindbaar, maar embedding-recall rangschikt het onder k -> een graaf-buur KAN dit oplossen;
  (b) de vraag is vaag, gebruikt woorden die niet in het document staan, of het document beantwoordt de vraag simpelweg niet -> niets lost dit op, en het blijft als permanente ruis in de set staan.

Alleen (a) is een geldig voor/na-instrument.

Werkwijze: bemonster documenten uit de vault, genereer per document een vraag, draai kb-eval.py --verbose, en sorteer op WAARGENOMEN RANG in plaats van op voorspelling. Rang 1-3 -> de 'werkt'-set. Rang 0 terwijl het document aantoonbaar het antwoord draagt -> de 'faalt'-set. Alles waarvan niet te verdedigen valt dat het document de vraag beantwoordt, valt af.

Sjabloon voor een goede negatieve case: 'Wat is de prioriteitsvolgorde van de gefaseerde data-inname strategie?' -> 09-memory/2026-06-27-gefaseerde-data-inname-strategie.md. Het bestand bestaat, de vraag parafraseert de titel, en recall geeft rang 0.

NIET de bestaande sets overschrijven: de baseline in TASK-67 is gekoppeld aan kb-eval-set.json en kb-memory-eval-set.json. Nieuwe sets als aparte bestanden.

PRIVACY: 06-claude staat in de whitelist van de vault-.gitignore en gaat dus mee naar de (private) GitHub-repo. De nieuwe vragen bevatten inhoud uit de geheugenlaag. Dezelfde afweging als bij TASK-67, maar expliciet te bevestigen in plaats van stilzwijgend over te nemen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Minimaal 10 vragen met waargenomen rang 1-3 ('werkt') en 10 met rang 0 waarvan verdedigbaar is dat het document het antwoord draagt ('faalt nu')
- [x] #2 Selectie gebeurt op gemeten rang, niet op voorspelling; de meetuitvoer per vraag is vastgelegd
- [x] #3 Nieuwe sets als aparte bestanden; kb-eval-set.json en kb-memory-eval-set.json blijven ongewijzigd zodat de TASK-67-baseline geldig blijft
- [x] #4 Voor elke faal-case staat genoteerd WAAROM het document het antwoord draagt, zodat latere lezers de case kunnen betwisten
- [x] #5 Baseline op de nieuwe sets gemeten en vastgelegd voor er iets aan de ranking verandert
- [ ] #6 Privacy-consequentie van eval-inhoud in 06-claude expliciet bevestigd
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
METING RONDE 1+2 (2026-07-25). 165 documenten bemonsterd (deterministische stap over gesorteerde lijst), 156 kandidaatvragen gegenereerd door 11 subagents, gemeten via kb_recall.recall_hits per laag - dezelfde route als de hook.

Rangverdeling memory (96 vragen):  1:40  2:20  3:2  4:4  5:5  0:25
Rangverdeling wiki   (60 vragen):  1:39  2:11  3:6  4:2  0:2

Ronde 2 kreeg de instructie om vanuit het SYMPTOOM te vragen in plaats van met de vaktermen uit het document. Effect op de geheugenlaag: van 5 naar 20 faalgevallen op 42 vragen. Dat is precies de bedoeling - de eerste ronde was te makkelijk omdat de vraag de titel parafraseerde.

Bevinding op zichzelf: de geheugenlaag is structureel slechter vindbaar dan de wiki-laag (25 van 96 mist tegen 2 van 60). Memories zijn kort en atomair, dus hun cosinus tegen een prompt ligt laag - daar bestaat de aparte MEMORY_MIN_COS-drempel al voor. Dat is ook de laag waar een graafbuur het meest kan toevoegen.

MEETFOUT ONDERSCHEPT, en dit had de hele set kunnen verpesten.

De eerste meting gaf 14 keer None terug in plaats van een rang. Als rang 0 geteld had dat 14 valse faalgevallen opgeleverd - een eval-set van meetfouten.

Oorzaak gemeten, niet geraden: qwen3-embedding:8b (~8 GB) wordt na inactiviteit uit VRAM gezet. Koude load duurt 28,2s; _embeddings.embed() heeft een timeout van 30,0s. Twee seconden marge. Warm is dezelfde call 0,46s.

Na hermeten met timeout 180s en keep_alive: alle 14 opgelost, waarvan 13 rang 1 of 2. Een ervan ('Waarom is een antwoord op de PR=A-prompt geen bewijs dat zenden werkt?') stond in de eerdere kb-eval-uitvoer als rang 0 en is in werkelijkheid rang 1.

BREDERE CONSEQUENTIE: kb-retrieve faalt open. Op een koude machine krijgt de gebruiker dus stil GEEN kennisinjectie, zonder enig signaal. De keep_alive-parameter in de embed-call bestaat hiervoor, maar elke andere aanroep zonder die parameter (ook een handmatige curl) reset hem naar de standaard 5 minuten. Verdient een eigen taak.

ADVERSARIELE VERIFICATIE van de 27 rang-0 gevallen (workflow, 12 agents, 591k tokens).

Twee onafhankelijke lenzen per geval:
  - WEERLEG: ga uit van 'de koppeling deugt niet', answerable=true alleen bij een aanwijsbare passage;
  - LEZER: zou iemand met deze vraag redelijkerwijs juist DIT document bedoelen, of passen andere even goed?

Uitslag: 24 beide akkoord | 0 beide afgewezen | 3 verdeeld.

De drie verdeelde gevallen vielen alle drie op hetzelfde probleem, gevonden door de lezer-lens:
  - 2026-07-02-esp32-s3-ble-scan-mode: near-duplicaat 2026-07-02-passive-continuous-ble-scanning.md uit dezelfde bronsessie
  - 2026-07-02-memory-recall-systeem: 2026-07-25-retrieval-procedure.md en -retrieval-pipeline.md dekken het 'hoe' beter (cosine >= 0,6, RRF k=60)
  - 2026-07-05-vmmemwsl-resource-accounting-2: BYTE-IDENTIEKE tweeling -accounting.md, beide status current

Deze drie zijn uit de faal-set gehouden: een case die geen enkele ranking kan winnen is geen meetinstrument. Het duplicatenprobleem zelf is doorgezet naar TASK-73.

V2-SETS OPGELEVERD in $VAULT/06-claude/ (alleen Kluis, niet upstream - expliciete gebruikersinstructie):
  kb-memory-eval-set-v2.json : 84 vragen (62 werkt, 22 faalt-nu)
  kb-eval-set-v2.json        : 58 vragen (56 werkt, 2 faalt-nu)
  README-eval-sets.md        : methode, velden, en de opwarm-waarschuwing voor het embedding-model

Elke entry draagt bucket (werkt|faalt-nu), baseline_rank (de gemeten rang op 2026-07-25) en why (welk inhoudelijk punt het antwoord draagt). Daarmee is een latere meting PER VRAAG vergelijkbaar in plaats van alleen op het aggregaat, en kan iedere case worden aangevochten zonder het document te herlezen.

BAsELINE op de v2-sets, gemeten voor er iets aan de ranking is veranderd:
  memory (84): @1 0.476 / @3 0.738 / @5 0.738, MRR 0.603
  wiki   (58): @1 0.672 / @3 0.966 / @5 0.966, MRR 0.802
Ter vergelijking v1: memory @3 0.941, wiki @3 1.000 - die zaten op het plafond.

ARTEFACT, eerlijk vastgelegd: @3 en @5 zijn identiek omdat ik de rang-4-en-5-gevallen (11 vragen) als bucket heb overgeslagen. Juist die zouden het verschil tussen @3 en @5 zichtbaar maken. De set kan @5 dus alleen bewegen via de rang-0-groep. Verdedigbaar, want daar moet de winst vandaan komen, maar het is een selectiekeuze en geen eigenschap van de data. Wie later @5-gevoeligheid wil, voegt die 11 gevallen toe.

kb-eval eist q en expect op ELKE entry; een toelichtingsblok als eerste element breekt de set (foutmelding: 'entry 0 mist q of expect'). Documentatie staat daarom in README-eval-sets.md ernaast.
<!-- SECTION:NOTES:END -->
