---
id: TASK-43
title: Release KennisBank v0.19.0 transcript-stripper
status: In Progress
assignee: []
created_date: '2026-07-24 13:39'
labels:
  - release
  - destilleer
dependencies:
  - TASK-42
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Publiceer een minor release (v0.19.0) met de transcript-stripper-feature uit PR #52 (task-42) bovenop v0.18.1. Doc-gedreven release: versie leeft in CHANGELOG.md + README-highlights + git-tag (geen VERSION-file). Volg de v0.18.1-blauwdruk (task-41) en de wiki release-tag-na-geverifieerde-merge: release-branch -> PR -> CI groen -> merge -> tag pas op de geverifieerde main-SHA -> publieke GitHub-release.

SemVer: nieuwe backward-compatible feature sinds v0.18.1 = minor bump naar 0.19.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Feature PR #52 (transcript-stripper) is in main met CI groen (2cc700a).
- [ ] #2 CHANGELOG.md, README.md en README.nl.md beschrijven v0.19.0 accuraat (alleen de stripper-feature, niet overdreven), inclusief bijgewerkte CHANGELOG compare-links.
- [ ] #3 De release-commit passeert de repository-CI op main.
- [ ] #4 Annotated tag v0.19.0 en een non-draft, non-prerelease GitHub-release wijzen naar de geverifieerde main-commit.
<!-- AC:END -->
