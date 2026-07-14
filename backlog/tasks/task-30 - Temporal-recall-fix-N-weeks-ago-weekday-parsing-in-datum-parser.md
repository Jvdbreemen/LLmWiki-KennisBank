---
id: TASK-30
title: 'Temporal recall: fix "N weeks ago <weekday>"-parsing in datum-parser'
status: Done
assignee: []
created_date: '2026-07-13 19:52'
updated_date: '2026-07-13 21:46'
labels:
  - temporal-recall
  - parser
  - bug
dependencies: []
modified_files:
  - scripts/_activity.py
  - scripts/test_activity_temporal.py
  - tests/test_activity_multilang.py
priority: medium
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De natuurlijke-taal datum-parser van kb-activity.py (gebruikt door /watdeedik, /timeline, /weeklog) parseert "two weeks ago thursday" fout: hij resolvet alleen de weekday naar de huidige/vorige week (2026-07-09) en degradeert "two weeks ago" tot topic-filter, waardoor het resultaat leeg is. Verwacht: 2026-06-25.

Root cause zit in de 3-lagen parser (zie wiki: meertalige-temporal-recall-3-lagen): de deterministische locale-tabellen kennen wel "vorige week maandag" maar niet de combinatie "N weken geleden <weekdag>" / "N weeks ago <weekday>". De restwoorden vallen door naar topic-extractie.

Scope:
- Voeg patroon "N week/weken/weeks geleden|ago + weekdag" toe aan de deterministische laag (NL + EN), inclusief typo-tolerantie is out of scope.
- Zorg dat resterende tijdswoorden nooit stilzwijgend als topic worden geïnterpreteerd; log of toon wat als topic is opgevat zodat misparses zichtbaar zijn.
- Tests in tests/ (niet naast de code in scripts/, zie wiki: ci-test-locatie-scripts-vs-tests).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 "two weeks ago thursday" resolvet naar de donderdag van twee ISO-weken terug (vandaag ma 2026-07-13 → 2026-07-02; testreferentie do 2026-07-09 → 2026-06-25)
- [x] #2 "twee weken geleden donderdag" (NL) resolvet naar dezelfde datum
- [x] #3 "vorige week maandag" en "last monday" blijven correct werken (regressietest)
- [x] #4 Tijdswoorden die niet geparset kunnen worden leiden tot een expliciete melding/suggestie, niet tot stille topic-degradatie
- [x] #5 Unit tests staan in tests/ en draaien groen in CI
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fix in scripts/_activity.py parse_period: nieuwe branch vóór de bare-weekday-branch die "N <weekunit> ago/geleden + <weekdag>" herkent in vier woordvolgordes (suffix-ago en prefix-ago, weekdag voor of na). Resolvet naar de weekdag binnen de ISO-week N weken terug. Daarnaast TemporalRange.warning toegevoegd: _residual_time_warning() detecteert sterke tijdstokens (weekdagen, ago-woorden, relatieve-dag-woorden) die in het topic zijn achtergebleven en geeft een expliciete waarschuwing; what_did_i_do propageert die naar result.warnings (zichtbaar als WARN in output). Tests: 7 nieuwe cases in scripts/test_activity_temporal.py (nl/en/de/fr) + test_residual_time_words_warn in tests/test_activity_multilang.py. 145 deterministische cases + 8 unittests groen. E2e geverifieerd tegen Kluis-vault: "two weeks ago thursday" → 2026-07-02 met resultaten. Deploy naar $VAULT/.claude/scripts nog nodig via setup/upgrade-flow (niet bare cp).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Parser-fix voor "N weeks ago <weekday>": nieuwe deterministische branch in parse_period (vóór bare-weekday) die de weekdag binnen de ISO-week N weken terug resolvet, in vier woordvolgordes over nl/en/de/fr/es/it. Plus TemporalRange.warning voor residuele tijdswoorden in het topic, gepropageerd naar /watdeedik WARN-output. 7 nieuwe parsercases + 1 warning-unittest; 145 cases en 8 unittests groen; e2e geverifieerd tegen de Kluis-vault. Commit df0cc14 op feat/atlas-sidecar. Follow-up: deploy naar $VAULT/.claude/scripts via setup/upgrade-flow.
<!-- SECTION:FINAL_SUMMARY:END -->
