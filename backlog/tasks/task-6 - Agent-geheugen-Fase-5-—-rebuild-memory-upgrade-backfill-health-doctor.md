---
id: TASK-6
title: Agent-geheugen Fase 5 — rebuild-memory + upgrade-backfill + health/doctor
status: Done
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 12:20'
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
- [x] #1 /kennisbank:rebuild-memory her-extraheert uit transcripts, vraagt bevestiging, idempotent
- [x] #2 Upgrade-backfill eenmalig over bestaande transcript-backlog
- [x] #3 doctor.sh no-cloud + quarantaine-rot (>48u unverified) checks
- [x] #4 Sessiestart toont sweep-health + achterstand
- [x] #5 Geen wiki->memory seeding
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase 5 afgerond. --all her-extractiemodus + /kennisbank:rebuild-memory (bevestigend, vrijwel-idempotent via semantische dedup, processt ALLE transcripts), memory-doctor.py (no-cloud: cloud-provider-detectie + gehard endpoint-check via urlparse+ipaddress.is_loopback + 'ollama' in chain; quarantaine-rot >48u), memory-notify.py SessionStart-health (luid bij model_unreachable/errors/rot/gestalde-heartbeat, stil gezond), upgrade-backfill in kennisbank-upgrade-skill. Commits 0700053, 509d90e, 44d32df, 6b7c60b + fix-wave 3ef9d1e. 222 tests groen. Whole-branch review (24 agents): 0 Critical, 4 Important GEFIXT (2 privacy-#4-endpoint-gaten, --all-completeness, stale-heartbeat-signaal) + minors. Geen wiki->memory seeding (keuze C). Geheugen-subsysteem compleet.
<!-- SECTION:FINAL_SUMMARY:END -->
