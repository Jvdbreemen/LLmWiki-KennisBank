---
id: TASK-80
title: >-
  Oriëntatie-summary bij sessiestart: counts + trending onderwerpen (idee uit
  Mind)
status: Done
assignee: []
created_date: '2026-07-26 14:14'
updated_date: '2026-07-26 19:13'
labels:
  - idee-gestolen
  - retrieval
milestone: Agent-geheugen
dependencies: []
references:
  - 'https://github.com/GabrielMartinMoran/mind'
priority: low
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Geleend van github.com/GabrielMartinMoran/mind: space_get geeft een goedkope oriëntatie-samenvatting (aantal memories, trending memories) als eerste context voor een agent.

KennisBank /sessiestart geeft al een sessie-check, maar geen compacte "wat leeft er in deze vault"-oriëntatie: aantallen per type, recent gewijzigde/veel geraadpleegde artikelen, actieve taken. Bouw dit als goedkope query op kb-index.db (geen embeddings, sub-seconde, hot-path-budget respecteren) en voeg toe aan /sessiestart en/of SessionStart-hookoutput.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Compacte oriëntatie: documentcounts per type, top-N recent gewijzigde artikelen, actieve backlog-taken
- [x] #2 Puur SQL op kb-index.db, geen embedding-call; runtime sub-seconde
- [x] #3 Geïntegreerd in /sessiestart (en optioneel SessionStart-hooktier, opt-in via settings)
- [x] #4 Output feitelijk en kort, geen log-ruis (noord-ster punt 4)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Merged via PR #77 (e060641 on origin/main). kb-orientation.py delivers a compact vault orientation (counts per layer, recent wiki articles, frequently used knowledge from kb-usage.db, open backlog tasks in the session cwd) with pure SQL reads — 0.2 s measured on a 1305-document vault. Integrated as a /sessiestart step plus an opt-in `orientation` toggle (default off) in the coordinator's NOTIFICATIONS phase, deliberately behind the freshness gate. Toggle registered on all four knob surfaces; 8 new tests. Copilot review unavailable (quota); replaced by a local review agent, which caught one real issue (missing .as_posix() in the sqlite file: URI) — fixed before merge. Bijvangst: fixed the test-isolation bug in test_activity_multilang.py that read the developer's real vault settings.
<!-- SECTION:FINAL_SUMMARY:END -->
