---
id: TASK-11
title: >-
  Setup + migratie v2 - idempotent-veilige setup.sh +
  version-stamp/migratie-framework
status: Done
assignee: []
created_date: '2026-06-27 21:11'
updated_date: '2026-06-27 23:28'
labels:
  - setup-migratie
dependencies: []
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Lerend van de agent-geheugen upgrade-deploy. Maak setup.sh idempotent-veilig voor nieuwe EN bestaande gebruikers. Spec: docs/superpowers/specs/2026-06-27-setup-migratie-v2-design.md. Plan: docs/superpowers/plans/2026-06-27-setup-migratie-v2.md (7 taken, TDD). Oplossing: _hooks_manifest single source + register-hooks interpreter-aware/matcher/self-heal-behoud/manifest + _settings.migrate additief + _migrations version-stamp .kennisbank-version/runner + setup.sh tooling-refresh-zonder-clobber + manifest-hookset + migraties + doctor.sh manifest-gedreven + versie-stamp. Versie 0.9.0.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Setup + migratie v2 afgerond (7 taken TDD + whole-branch review + fix-wave). _hooks_manifest single source; register-hooks interpreter-aware (py-3 Windows/python3 elders) + matcher + self-heal-behoud-interpreter + --manifest; _settings.migrate additief (weigert corrupte JSON); _migrations version-stamp .kennisbank-version + runner (fail-voor-stamp, downgrade-guard, soft-skip bij corrupte globale settings); setup.sh idempotent-veilig (tooling-refresh zonder user-data-clobber, volledige hookset, pip naar juiste interpreter, migraties); doctor.sh manifest-gedreven + versie. Versie 0.9.0. Commits 4ff4007..f343405. Whole-branch review (24 agents, 4 dim): 0 Critical, 8 Important + 6 Minor -> fix-wave f343405 (alle Important + 3 Minor). Tests: deploy 21/21 (echte setup.sh), full ~400 groen (1 pre-existing Windows safe-edit-flake, groen in CI). Gepusht feat/setup-migratie-v2.
<!-- SECTION:FINAL_SUMMARY:END -->
