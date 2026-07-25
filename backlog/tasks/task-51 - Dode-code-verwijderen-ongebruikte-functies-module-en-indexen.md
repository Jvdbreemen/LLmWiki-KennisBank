---
id: TASK-51
title: 'Dode code verwijderen: ongebruikte functies, module en indexen'
status: Done
assignee: []
created_date: '2026-07-25 03:34'
updated_date: '2026-07-25 07:50'
labels:
  - tech-debt
  - cleanup
dependencies: []
priority: medium
ordinal: 65000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Opruiming van code die door een verificatieronde met tegenbewijs-agents is bevestigd als onbereikbaar. Elk item is gecontroleerd op verwijzingen vanuit Python, markdown slash-commands, skills, `setup.sh`, `doctor.sh`, CI, de client-configuratieschrijvers en de tests.

Te verwijderen:
- `assistant_text()` in `scripts/kb-usage-scan.py` — nul aanroepers; de scan gebruikt de tool-input-variant. De functie is bij een eerdere splitsing bewust versmald. Corrigeer in dezelfde wijziging de module-docstrings die nog beloven dat vermeldingen in assistant-tekst als gebruik tellen.
- De aggregator `iter_activity_events` en de vier extractorfuncties eronder in `scripts/_activity.py` — nul aanroepers in de volledige geschiedenis. Het live pad loopt via de bronbestandenlijst naar de per-bron-extractie; de dode functies zijn bijna letterlijke duplicaten daarvan.
- `scripts/eval-wiki-recall.py` — nul aanroepers, en de bestandsnaam met koppelteken maakt de module onimporteerbaar. Verwijderen stopt bovendien de uitrol ervan naar elke gebruikersvault.
- `restore_backup()` in `scripts/_copilot.py` — alleen door een test aangeroepen; de echte rollback loopt via de remove-functie.
- De api-key-omgevingstak in `scripts/_llm.py` — één treffer in de hele repo, namelijk de lezing zelf. Geen schrijver, geen documentatie, geen test, en `AGENTS.md` somt de toegestane sleutels op en sluit deze uit.
- Twee SQLite-indexen in `scripts/_activity.py` die de queryplanner in geen enkele echte query kiest, omdat er in Python op wordt gefilterd.

**KRITIEK — niet verwijderen, ook al lijkt het erop.** `iter_usage_events` staat visueel middenin het dode blok maar is live via de per-bron-extractie. Een sweep die "de hele familie" weghaalt sloopt hem, en geen enkele test vangt dat. Verder blijven onaangeroerd: `activity-locales.json` (data-only, dus onvindbaar met symbol-greps), `build-karpathy-index.py` (draait als job en de output wordt door twee prompts gelezen), de legacy-hook-opruimlijst, en de drempelconstante in `kb-calibrate.py` (die moet gecorrigeerd, niet geschrapt).

Bij het trimmen van de test voor de copilot-backup: alleen de assertie op de restore-functie weghalen. De regels erboven zijn de enige dekking van de backup-functie zelf, die zes aanroepplaatsen heeft.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 De zes genoemde symbolen en de module zijn verwijderd, in één samenhangende wijziging
- [x] #2 `iter_usage_events` bestaat nog en de per-bron-extractie werkt onveranderd; een test dekt die aanroeppad expliciet
- [x] #3 De twee ongebruikte indexen zijn uit de schemadefinitie verwijderd zonder de schemaversie te bumpen
- [x] #4 Docstrings die naar verwijderde functionaliteit verwijzen zijn gecorrigeerd naar wat de code doet
- [x] #5 De test voor de copilot-backup dekt nog steeds de backup-functie zelf; alleen de assertie op de verwijderde restore is weg
- [x] #6 CHANGELOG en backlog-historie zijn niet herschreven
- [x] #7 De volledige testsuite draait groen
<!-- AC:END -->
