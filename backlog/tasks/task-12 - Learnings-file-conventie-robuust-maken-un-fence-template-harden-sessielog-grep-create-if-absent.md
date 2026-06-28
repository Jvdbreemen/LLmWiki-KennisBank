---
id: TASK-12
title: >-
  Learnings-file conventie robuust maken (un-fence template + harden /sessielog
  grep + create-if-absent)
status: Done
assignee: []
created_date: '2026-06-28 05:59'
updated_date: '2026-06-28 06:04'
labels:
  - sessielog
  - docs
dependencies: []
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De LEARNINGS_FILE-conventie was dubbelzinnig: de regel stond als voorbeeld binnen een code-fence in CLAUDE.md.template, waardoor /sessielog stap 5 'm stil oversloeg (geconstateerd toen een sessie de learnings-append miste terwijl ~/Claude/learnings.md bestond + geconfigureerd was). Fix (opt-in-maar-robuust): (1) CLAUDE.md.template levert een duidelijke gecommente LEARNINGS_FILE-regel (remove # to enable) ipv fenced voorbeeld; (2) commands/sessielog.md stap 5 greppt expliciet de eerste ongecommente ^LEARNINGS_FILE=-regel uit $VAULT/CLAUDE.md, expandeert ~, en maakt het bestand aan als het ontbreekt; (3) POST-INSTALL.md + CHANGELOG bijwerken. Geen code-logica, geen auto-scaffold van het bestand bij setup (blijft door gebruiker beheerd; /sessielog maakt het bij eerste append). Complementair aan de automatische 09-memory-laag.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Learnings-file conventie robuust gemaakt. CLAUDE.md.template: gecommente opt-in-regel (remove '# ' to enable) i.p.v. fenced voorbeeld. commands/sessielog.md stap 5: leest deterministisch de eerste ongecommente ^LEARNINGS_FILE=-regel uit vault-CLAUDE.md, expandeert ~, maakt het bestand aan als het ontbreekt; skip alleen als niets geconfigureerd. POST-INSTALL.md + CHANGELOG bijgewerkt. Geen auto-scaffold (bestand blijft user-beheerd; complementair aan 09-memory). Grep-semantiek beide kanten geverifieerd. PR #18, CI groen. Docs/prompt-only, geen test raakt LEARNINGS.
<!-- SECTION:FINAL_SUMMARY:END -->
