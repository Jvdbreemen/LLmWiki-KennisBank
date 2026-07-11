---
id: TASK-27.10
title: Atlas - /atlas command, idle-hook, doctor, setup en docs
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - command
  - hook
  - doctor
  - setup
  - docs
dependencies:
  - TASK-27.4
parent_task_id: TASK-27
priority: high
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak de Atlas bruikbaar en onderhoudbaar als eerste-klas KennisBank-feature:
command, optionele idle-regeneratie, doctor-check, setup-deploy en documentatie.

Onderdelen:
- `/atlas` command (commands/atlas.md) dat `atlas-export.py` + `build-atlas.py`
  draait en `<vault>/.claude/atlas.html` schrijft; toont het pad en een korte
  status (tellingen). Geen zware verwerking op de hot path.
- Optionele idle-hook/toggle in de stijl van `daily_graphify`
  (`kennisbank-settings.json`), zodat de Atlas hoogstens eens per dag/idle
  wordt ververst; default uit of laag-frequent, fail-open.
- `doctor.sh` uitbreiden: rapporteer of `atlas.html` bestaat, of het vers is
  t.o.v. de source-watermarks/vault-mtimes, en de gebruikte generator-versie.
- `setup.sh`/`install-agent-envs.py`: deploy scripts + command voor de gekozen
  agents (claude/codex/opencode) analoog aan bestaande commands.
- Documentatie: README (nieuwe sectie "Visualisatie: de Atlas"), en waar
  relevant OBSIDIAN.md (Atlas als repo-native alternatief) en
  vault-structure/README.md (`.claude/atlas.html`).
- MCP: geen nieuwe verplichte tool nodig; noem alleen dat Atlas een
  mens-surface is, geen agent-surface.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `/atlas` genereert `<vault>/.claude/atlas.html` en print pad + status. Bewijs: run het command in een fixture-vault; het bestand bestaat en de output toont tellingen; het bestand opent offline (hergebruik 26.3-test).
- [ ] #2 De idle-toggle bestaat in `kennisbank-settings.json` en respecteert on/off + frequentie; uit betekent geen automatische regeneratie. Bewijs: test met toggle off verifieert dat geen regeneratie plaatsvindt; on verifieert hoogstens de afgesproken frequentie.
- [ ] #3 `doctor.sh` rapporteert aanwezigheid + staleness van de Atlas. Bewijs: doctor-run toont een atlas-regel; een test maakt de bron nieuwer en verifieert dat doctor "stale" meldt.
- [ ] #4 `setup.sh` deployt het command/scripts voor de gekozen agents. Bewijs: non-interactieve setup-run in een sandbox plaatst commands/atlas.md en de scripts op de juiste locaties; validatie faalt niet.
- [ ] #5 Docs beschrijven de Atlas als soevereine, repo-native visualisatie (geen Obsidian/plugin nodig). Bewijs: README bevat de nieuwe sectie met run-instructie en privacy-notitie.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 End-to-end verificatie (skill `verify`/`run`): `/atlas` in een sample-vault -> open `atlas.html` headless offline -> shell + MVP-lenzen renderen; screenshot als bewijs.
- [ ] #2 Doctor- en toggle-gedrag hebben tests (aanwezig/stale, on/off).
- [ ] #3 Setup-deploy is idempotent en herstelt/actualiseert bij her-run (upgrade-pad).
- [ ] #4 Documentatie is consistent met de daadwerkelijke command-naam en paden; geen dode verwijzingen.
<!-- DOD:END -->
