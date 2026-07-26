---
id: TASK-77
title: 'Testsuite draait setup.sh 18 keer: ~12,6 minuten per volledige run'
status: To Do
assignee: []
created_date: '2026-07-25 22:38'
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
- [ ] #1 test_setup_deploy draait setup.sh niet vaker dan nodig; het aantal runs staat expliciet in de code toegelicht
- [ ] #2 Volledige suite past binnen een enkel voorgrondvenster (< 10 minuten), gemeten
- [ ] #3 Tests die de installatie muteren delen geen fixture met tests die alleen inspecteren
- [ ] #4 Dezelfde 22 tests dekken nog steeds hetzelfde gedrag
- [ ] #5 Volledige suite groen
<!-- AC:END -->
