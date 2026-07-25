---
id: TASK-45
title: >-
  Hot-path noodstop: vec0-KNN-plafond, lege-vocabulaire-sentinel en
  locale-deploy
status: Done
assignee: []
created_date: '2026-07-25 03:32'
updated_date: '2026-07-25 07:50'
labels:
  - bug
  - hot-path
  - retrieval
  - temporal
dependencies: []
priority: high
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Drie defecten die samen de twee kernfuncties van KennisBank (retrieval en temporele recall) stil kapot maken. Ze horen in één taak omdat ze alledrie "faalt zonder foutmelding" zijn en dezelfde release nodig hebben.

**1. vec0-KNN-plafond (`scripts/_kbindex.py:129`).** `pool = min(max(k * 4, 20, total), 5000)`. De sqlite-vec vec0-extensie accepteert maximaal `k=4096`; daarboven gooit de KNN-query een `OperationalError`. Die gooi valt buiten de enige `try` in `search()` (die dekt alleen het FTS-deel), propageert naar `kb-recall.recall_hits:115` en levert `[]`. Gevolg: zodra de vault boven ~1024 docs komt (pool = k*4) gaat memory-recall volledig en geruisloos dood. Geen log, geen exit-code, geen doctor-signaal. De vault van de auteur zit op 1214 docs en groeit.

**2. Lege alternatie matcht de lege string (`scripts/_activity.py:1121`).** `_alt()` bouwt een regex-alternatie uit een woordenset. Bij een lege set levert het `""`, wat compileert tot `\b(?:)\b` — en dat matcht de lege string op elke woordgrens. Elke tak van de datumparser vuurt dan, en elke temporele vraag krijgt hetzelfde foute bereik op confidence 0.95, inclusief expliciete ISO-datums.

**3. `activity-locales.json` wordt nooit gedeployed (`setup.sh:184`).** De glob is `scripts/*.py scripts/*.sh`; `git log -S'scripts/*.json'` geeft nul commits. `_activity.py` resolvet `_LOCALES_PATH` naast zichzelf zonder repo-relatieve fallback. Elke schone installatie draait dus met een lege Laag-1-vocabulaire. In combinatie met defect 2 is dat niet degraderend maar fout: `/watdeedik`, `/weeklog`, `/timeline` en de vier temporele MCP-tools collapsen naar één weekend. CI ziet het niet omdat die vanuit de repo-root draait, waar het bestand wel naast `_activity.py` staat.

Volgorde binnen de taak: fix 2 vóór of samen met fix 3, zodat een missende locale-tabel gedegradeerd raakt in plaats van fout.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `pool` in `_kbindex.search` overschrijdt nooit 4096, ook niet bij een corpus van 9999 docs; de `total`-term blijft behouden zodat de layer-starvation-fix uit TASK-10 intact blijft
- [x] #2 `tests/test_kbindex_search.py` bevat een test die vandaag rood is en die assert dat de pool-expressie bij `total=9999` ten hoogste 4096 oplevert
- [x] #3 `_alt([])` levert een nooit-matchende sentinel op in plaats van een lege string; `re.search(r'\b(?:' + _alt([]) + r')\b', 'gisteren')` geeft None
- [x] #4 `tests/test_activity_multilang.py` bevat een test die vandaag rood is op de lege-vocabulaire-case
- [x] #5 `setup.sh` deployt `scripts/*.json` mee naar de vault; `chmod +x` blijft beperkt tot .py en .sh
- [x] #6 `tests/test_setup_deploy.py` assert dat `activity-locales.json` na een install in de vault-scriptsmap staat; deze test is vandaag rood
- [x] #7 `doctor.sh` rapporteert de omvang van de GELADEN locale-vocabulaire (niet de aanwezigheid van het bestand) en geeft WARN bij een lege tabel; geen FAIL, want `set -e` breekt setup.sh dan vóór het dashboard
- [x] #8 `skills/kennisbank-upgrade/SKILL.md` noemt de json-bestanden in de te kopiëren set
- [x] #9 De volledige testsuite draait groen
<!-- AC:END -->
