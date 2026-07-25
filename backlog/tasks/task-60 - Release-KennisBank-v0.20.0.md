---
id: TASK-60
title: Release KennisBank v0.20.0
status: In Progress
assignee: []
created_date: '2026-07-25 05:20'
labels:
  - release
dependencies: []
priority: high
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Uitbrengen van de onderhoudsrelease die voortkomt uit de volledige codebase-analyse: TASK-45 t/m 54 en 59.

Inhoud: drie stille faalmodi op kernpaden (vec0-KNN-plafond, lege regex-alternatie in de datumparser, nooit-gedeployde locale-tabel), het schrijfpad naar gecureerde wiki-content dat zichzelf kon blokkeren, vier write-only tabellen met migratie, verwijderde dode code, een testsuite die eindelijk volledig verzameld wordt, en documentatiecorrecties met een lint die de drift structureel vangt.

Versie: minor, niet patch. Er worden tabellen gedropt op bestaande vaults, de MCP-rollup rapporteert een ander cache-veld, `setup.sh` deployt een extra bestandsglob en er komt een ontwikkelafhankelijkheid bij.

Procedure: branch naar de fork pushen, pull request naar upstream, mergen, taggen op de gemergede commit en een GitHub-release publiceren. De tag hoort pas geplaatst te worden nadat feitelijk is vastgesteld dat de doelbranch de release-inhoud bevat — niet op de branch-tip in de veronderstelling dat de merge geslaagd is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De volledige testsuite draait groen vóór de push; geen enkele stap naar buiten gebeurt op een ongeverifieerde boom
- [ ] #2 CHANGELOG bevat een 0.20.0-sectie met de compare-links bijgewerkt, en beide README-varianten noemen dezelfde versie en dezelfde feiten
- [ ] #3 De branch staat op de fork en er is een pull request naar upstream met een beschrijving die de dragende wijzigingen benoemt
- [ ] #4 De pull request is gemerged in upstream main
- [ ] #5 De tag v0.20.0 staat op de commit die feitelijk in upstream main zit, geverifieerd na de merge
- [ ] #6 Er is een GitHub-release gepubliceerd met de changelog-inhoud
- [ ] #7 TASK-45 t/m 54 en 59 staan op Done
<!-- AC:END -->
