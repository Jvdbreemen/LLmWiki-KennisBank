---
id: TASK-43
title: Release KennisBank v0.19.0 transcript-stripper
status: Done
assignee: []
created_date: '2026-07-24 13:39'
updated_date: '2026-07-24 14:04'
labels:
  - release
  - destilleer
dependencies:
  - TASK-42
references:
  - 'https://github.com/Jvdbreemen/LLmWiki-KennisBank/pull/53'
  - 'https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.19.0'
modified_files:
  - CHANGELOG.md
  - README.md
  - README.nl.md
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Publiceer een minor release (v0.19.0) met de transcript-stripper-feature uit PR #52 (task-42) bovenop v0.18.1. Doc-gedreven release: versie leeft in CHANGELOG.md + README-highlights + git-tag (geen VERSION-file). Volg de v0.18.1-blauwdruk (task-41) en de wiki release-tag-na-geverifieerde-merge: release-branch -> PR -> CI groen -> merge -> tag pas op de geverifieerde main-SHA -> publieke GitHub-release.

SemVer: nieuwe backward-compatible feature sinds v0.18.1 = minor bump naar 0.19.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Feature PR #52 (transcript-stripper) is in main met CI groen (2cc700a).
- [x] #2 CHANGELOG.md, README.md en README.nl.md beschrijven v0.19.0 accuraat (alleen de stripper-feature, niet overdreven), inclusief bijgewerkte CHANGELOG compare-links.
- [x] #3 De release-commit passeert de repository-CI op main.
- [x] #4 Annotated tag v0.19.0 en een non-draft, non-prerelease GitHub-release wijzen naar de geverifieerde main-commit.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
KennisBank v0.19.0 gepubliceerd (2026-07-24). Doc-gedreven minor release met de transcript-stripper (task-42, PR #52).

Uitgevoerd volgens de release-tag-na-geverifieerde-merge-discipline:
- Release-metadata (CHANGELOG.md [0.19.0] + compare-links, README.md + README.nl.md highlights) op branch release/v0.19.0.
- PR #53 -> upstream CI groen -> squash-merge naar main (82499b0).
- CI opnieuw groen geverifieerd op de gemergde SHA 82499b0 (run 30099116552) VOOR het taggen.
- Annotated tag v0.19.0 (object e03eacd) op 82499b0 gepusht; peeled remote-target geverifieerd = 82499b0.
- GitHub-release v0.19.0 aangemaakt: non-draft, non-prerelease, latest. https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.19.0
- Lokale main gesynct naar origin/main; release-branch (lokaal + remote) opgeruimd.

Geen code-wijzigingen in de release; de feature landde in #52. Versie leeft in CHANGELOG + README-highlights + git-tag (geen VERSION-file).
<!-- SECTION:FINAL_SUMMARY:END -->
