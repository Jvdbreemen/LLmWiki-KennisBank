---
id: TASK-6
title: Agent-geheugen Fase 5 — rebuild-memory + upgrade-backfill + health/doctor
status: In Progress
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 11:27'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-5
references:
  - docs/superpowers/plans/2026-06-27-agent-geheugen-fase5-rebuild-health.md
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
/kennisbank:rebuild-memory (zware her-extractie uit transcripts, vraagt bevestiging, idempotent via dedup). Upgrade-backfill: kennisbank-upgrade draait rebuild-memory eenmalig over bestaande transcript-backlog. doctor.sh: no-cloud-check (geen externe host-calls) + quarantaine-rot-check (N memories unverified >48u). Sessiestart-health: sweep-gezondheid + achterstand. Geen wiki->memory seeding (keuze C).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /kennisbank:rebuild-memory her-extraheert uit transcripts, vraagt bevestiging, idempotent
- [ ] #2 Upgrade-backfill eenmalig over bestaande transcript-backlog
- [ ] #3 doctor.sh no-cloud + quarantaine-rot (>48u unverified) checks
- [ ] #4 Sessiestart toont sweep-health + achterstand
- [ ] #5 Geen wiki->memory seeding
<!-- AC:END -->
