---
id: TASK-77
title: 'Testsuite draait setup.sh 18 keer: ~12,6 minuten per volledige run'
status: Done
assignee: []
created_date: '2026-07-25 22:38'
updated_date: '2026-07-26 09:57'
labels:
  - tests
  - developer-experience
  - performance
dependencies: []
references:
  - 'tests/test_setup_deploy.py:83'
  - 'tests/test_setup_deploy.py:241'
  - setup.sh
priority: medium
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
tests/test_setup_deploy.py roept run_setup() aan als METHODE per test, niet als gedeelde fixture. Elke aanroep draait `bash setup.sh --yes --skip-model-check` in een verse temp-HOME.

GEMETEN 2026-07-26:
  een enkele setup.sh-run            42 s
  aanroepen van run_setup() in de module  18
  test_setup_deploy totaal           ~12,6 minuten (3 batches: 318 s + 342 s + 261 s = 921 s voor 22 tests)
  rest van de suite (863 tests)      ~200 s

Gevolg: een volledige `python3 -m unittest discover -s tests` duurt ~17 minuten en past niet in een voorgrondvenster. Twee achtergrondruns werden onderweg afgeschoten, waardoor er twee keer GEEN uitslag was. Dat is niet alleen traag; het maakt 'suite groen' duur om te bewijzen, en wat duur is te bewijzen wordt in de praktijk overgeslagen.

De tests controleren bijna allemaal DEPLOY-UITKOMSTEN (staat bestand X in de vault, staat hook Y in settings) op een installatie die per test identiek is. Die delen prima één installatie.

RICHTING: setUpClass met een gedeelde temp-HOME voor de tests die alleen uitkomsten inspecteren; een eigen run behouden voor de tests die de installatie zelf variëren (hernieuwde run, geweigerde hooks, idempotentie). Verwachting op basis van de meting: van ~921 s naar ruwweg 42 s plus de paar tests die echt een eigen run nodig hebben.

LET OP bij uitvoer: gedeelde state tussen tests introduceert precies het soort volgorde-afhankelijkheid dat elders in deze suite al een flaky test opleverde. Tests die de installatie MUTEREN mogen de gedeelde fixture niet gebruiken.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 test_setup_deploy draait setup.sh niet vaker dan nodig; het aantal runs staat expliciet in de code toegelicht
- [x] #2 Volledige suite past binnen een enkel voorgrondvenster (< 10 minuten), gemeten
- [x] #3 Tests die de installatie muteren delen geen fixture met tests die alleen inspecteren
- [x] #4 Dezelfde 22 tests dekken nog steeds hetzelfde gedrag
- [x] #5 Volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
UITGEVOERD 2026-07-26.

Een gedeelde installatie voor de tests die de deploy alleen LEZEN; eigen run voor alles wat muteert.

GEMETEN:
  test_setup_deploy      921 s -> 340 s
  volledige suite      ~17 min -> 7m41s, 890 tests groen, in EEN voorgrondrun

Dat laatste is AC #2: de suite paste eerder niet in een venster, waardoor twee achtergrondruns onderweg werden afgeschoten en er twee keer geen uitslag was.

SCHEIDING, expliciet en niet op gevoel:

GEDEELD (16 tests) -- stellen uitsluitend vast DAT iets gedeployed is. Ook de drie doctor-tests zitten hierin, na controle dat scripts/doctor.sh geen enkele schrijfactie doet (geen mkdir/touch/cp/mv/rm; de treffers op '>' waren allemaal 2>/dev/null).

EIGEN RUN (6 runs) -- muteren de installatie: settings.json weggooien, setup twee keer draaien voor idempotentie, een bestaande settings.json vooraf neerzetten, hernieuwde run, geweigerde hooks. Die delen niets. Gedeelde state tussen muterende tests zou precies de volgorde-afhankelijkheid opleveren die in deze suite al een keer een flaky test heeft veroorzaakt (test_a_killed_cycle_recovers_within_one_ceiling).

WAAROM GEEN KOPIE van de installatie per test, wat nog goedkoper zou zijn: de gedeployde settings.json bevat ABSOLUTE paden naar de temp-HOME. Een kopie op een ander pad zou naar de oorspronkelijke map blijven wijzen, en dan toetsen de doctor-tests de verkeerde boom terwijl ze groen blijven. Paden herschrijven in een gedeployde boom is precies het soort slimme-in-plaats-van-heldere oplossing dat hier niet hoort.

De resterende ~340 s is niet verder omlaag te brengen zonder de dekking te raken: idempotentie vraagt per definitie twee runs, de hernieuwde-run-test ook.

Dezelfde 22 tests, dezelfde asserties, alle groen.

CI groen op PR #68 (test, 1m21s), gemerged in main. Taak afgerond.
<!-- SECTION:NOTES:END -->
