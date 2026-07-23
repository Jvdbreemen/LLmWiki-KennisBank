---
id: TASK-39
title: 'SessionStart-hook: waarschuw bij branch achter upstream'
status: Done
assignee: []
created_date: '2026-07-23 21:24'
updated_date: '2026-07-23 21:53'
labels:
  - hook
  - git
  - automation
dependencies: []
modified_files:
  - scripts/git-upstream-check.py
  - scripts/kb-session-start.py
  - tests/test_session_start.py
priority: medium
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Local main dreef 72 commits achter origin/main omdat main alleen via handmatige `git pull --ff-only` bijwerkt en dat 11 dagen stil viel. Root cause: sync-discipline vereist handwerk (botst met noord-ster #3 automatiseren-boven-handwerk). Los op met een SessionStart-hook die cwd-aware een `git fetch` doet (korte timeout, fail-open) en compact waarschuwt als de huidige branch en/of main N commits achter de upstream staat.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Hook draait bij SessionStart, cwd-aware: doet niets als cwd geen git-repo met upstream is
- [x] #2 git fetch met korte timeout; bij netwerk-/git-fout blijft de hook stil (fail-open, blokkeert nooit)
- [x] #3 Waarschuwt compact in de context als huidige branch of main >= drempel achter upstream staat
- [x] #4 Interpreter-conventie: py -3 op Windows
- [x] #5 Geen ruis als alles up-to-date is
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
git-upstream-check verhuisd van gitignored .claude/ naar canonical scripts/git-upstream-check.py (tracked) en gevouwen als NOTIFICATIONS-job in de kb-session-start coordinator. Daardoor: (a) version-controlled, (b) via _copytree/setup automatisch gedeployed, (c) alle clients (Claude/Codex/Copilot) krijgen 'm gratis want ze wiren dezelfde coordinator als enige SessionStart-hook, (d) erft de 300s freshness-gate -> geen git-fetch-spam per sessie. Script blijft cwd-aware + fail-open (stil buiten repo of up-to-date). Repo-lokale .claude/settings.json teruggezet naar {} (gitignored, voorkwam dubbel-fire). Tests toegevoegd: job zit in NOTIFICATIONS, warning surfacet via relevant_report, clean is stil. 25 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
