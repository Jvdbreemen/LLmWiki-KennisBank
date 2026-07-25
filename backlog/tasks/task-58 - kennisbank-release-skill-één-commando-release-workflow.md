---
id: TASK-58
title: 'kennisbank-release skill: één-commando release-workflow'
status: To Do
assignee: []
created_date: '2026-07-23 22:16'
labels:
  - skill
  - release
  - automation
  - dx
dependencies: []
references:
  - backlog/tasks/task-35 - Release-KennisBank-v0.17.0.md
  - skills/kennisbank-upgrade/SKILL.md
  - CHANGELOG.md
priority: medium
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Releasen van LLmWiki-KennisBank is nu volledig handmatig (geen script/skill/CI-release-job). De v0.18.0-release deed dit met de hand: CHANGELOG-sectie + compare-links, README/README.nl highlights bumpen, focused tests, main pushen, tag, GitHub-release publiceren. Foutgevoelig en niet-idempotent. Maak een `kennisbank-release` skill (trigger /kennisbank-release) die de gedocumenteerde procedure uit de release-taken (v0.16.0/v0.17.0/v0.18.0) codificeert.

Kernstappen die de skill moet automatiseren:
1. Bepaal huidige tag + stel volgende versie voor (semver: fix->patch, feature->minor); vraag bevestiging bij twijfel.
2. Verzamel de commit-delta sinds de laatste tag (git log LAST..HEAD) als bron voor de changelog-sectie.
3. Genereer/plaats CHANGELOG.md sectie (Keep-a-Changelog: Added/Changed/Fixed, gedateerd) + update compare-links (Unreleased + nieuwe versie).
4. Bump README.md + README.nl.md feature-highlights naar de nieuwe versie.
5. Draai focused tests + docs-check; stop bij rood.
6. Commit release-docs, push main, maak annotated tag, push tag.
7. Publiceer GitHub-release met de changelog-sectie als notes (gh release create).
8. Bied aan de vault te upgraden via /kennisbank-upgrade (deployt vanaf de nieuwe tag).

Randvoorwaarden: pre-flight clean-state + CI-groen check op main vóór tag; werkt tegen origin (Jvdbreemen upstream); idempotent waar mogelijk; nooit taggen op ongemergede branch. Overweeg dry-run (--dry-run) zoals kennisbank-upgrade. Naslag: bestaande release-taken TASK-32/33/35 en de kennisbank-upgrade skill als structuur-sjabloon.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Skill /kennisbank-release bestaat in skills/kennisbank-release/SKILL.md en is via de manifest/deploy vindbaar
- [ ] #2 Automatiseert: versie-voorstel, CHANGELOG-sectie + compare-links, README/README.nl highlight-bump
- [ ] #3 Pre-flight: clean-state + CI-groen op main; weigert taggen op ongemergede branch
- [ ] #4 Draait focused tests + docs-check en stopt bij rood
- [ ] #5 Commit release-docs, push main, annotated tag, push tag, gh release create met changelog als notes
- [ ] #6 Biedt na afloop de vault-upgrade aan (/kennisbank-upgrade vanaf de nieuwe tag)
- [ ] #7 Ondersteunt --dry-run: toont geplande versie/changelog/acties zonder writes of push
<!-- AC:END -->
