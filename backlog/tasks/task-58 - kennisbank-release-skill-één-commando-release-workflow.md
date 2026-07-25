---
id: TASK-58
title: 'kennisbank-release skill: één-commando release-workflow'
status: To Do
assignee: []
created_date: '2026-07-23 22:16'
updated_date: '2026-07-25 05:56'
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
- [ ] #8 Wacht op de Copilot-review van de PR en verwerk die vóór merge en vóór tag; de review-comments zitten niet in `gh pr view` maar in `gh api repos/OWNER/REPO/pulls/N/comments`
- [ ] #9 Verifieert na de merge dat origin/main de commits feitelijk bevat, en tagt op die SHA — nooit op een branch-tip in de aanname dat de merge geland is
- [ ] #10 Schrijft release-notes met expliçiete UTF-8-encoding en een absoluut pad; verifieert daarna dat de gepubliceerde body niet leeg is (`gh release view --json body`)
- [ ] #11 Kiest merge-commit boven squash wanneer de branch bewust één commit per taak heeft en losse reverts waarde hebben
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Claude (v0.20.0-release)
created: 2026-07-25 05:56
---
Ervaringen uit de handmatige v0.20.0-release (2026-07-25) die de skill moet afvangen:

1. COPILOT-REVIEW. Ik mergede PR #54 voordat ik de Copilot-review las. Alle vijf opmerkingen waren terecht, waaronder een gat in een guard die in diezelfde PR was geschreven. CI was groen -- CI toetst gedrag, niet of een guard dekt wat hij beweert te dekken. De review-comments zijn NIET zichtbaar via `gh pr view`; gebruik `gh api repos/OWNER/REPO/pulls/N/comments --jq '.[] | \"=== \\(.path):\\(.line // .original_line)\\n\\(.body)\"'`.

2. RELEASE-NOTES LEEG GEPUBLICEERD. Het genereerscript viel om op cp1252 (`UnicodeEncodeError` op een minteken) en schreef nul bytes; `gh release create --notes-file` accepteerde dat zonder klagen. Daarna bleek `--notes-file /tmp/...` bovendien een ander bestand te lezen dan Python schreef: Python's `/tmp` is `C:\\tmp\\`, Git Bash mapt het elders. Schrijf met `io.open(..., encoding='utf-8')` naar een absoluut pad en verifieer daarna `gh release view --json body -q '.body|length'`.

3. MERGE-METHODE. De repo kent beide conventies (PR #41-45 merge-commits, #48-53 squash). Bij een branch met bewust één commit per taak is merge-commit de juiste keuze: bij een release met schema-migratie wil je één tabel-drop kunnen terugdraaien zonder de rest te raken.

4. CI-DUUR. De suite duurt ~20 min op Windows en 2m30s op de Linux-runner. Baseer een timeout-marge op de runner-meting, niet op de lokale.
---
<!-- COMMENTS:END -->
