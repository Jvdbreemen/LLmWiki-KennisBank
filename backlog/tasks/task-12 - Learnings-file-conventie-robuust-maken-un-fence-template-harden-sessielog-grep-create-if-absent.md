---
id: TASK-12
title: >-
  Learnings-file conventie robuust maken (un-fence template + harden /sessielog
  grep + create-if-absent)
status: In Progress
assignee: []
created_date: '2026-06-28 05:59'
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
