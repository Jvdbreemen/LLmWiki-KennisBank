---
id: TASK-5
title: >-
  Agent-geheugen Fase 4 — capture & sweep (extractie + onafhankelijke judge +
  onderhoud)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 08:10'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies:
  - TASK-3
  - TASK-4
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SessionStart-sweep (gegate op memory_capture): extraheer kandidaat-memories uit nieuwe transcripts, dedup, onafhankelijke verse-context judge (hoge zekerheid -> current, twijfel -> unverified), cross-memory onderhoud (supersede/expire/cluster + hercontrole). Trigger-agnostisch (SessionStart + /sessielog). render() input-hardening (uitgesteld uit fase 1). LET OP: judge-uitvoeringsmechanisme (detached/headless, niet-blokkerend bij SessionStart) eerst met advisor beslechten vóór planning. LLM-call als mockbare seam; deterministische plumbing unit-getest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Sweep extraheert+judget nieuwe transcripts, verse-context (onafhankelijk van producent)
- [ ] #2 Judge faalt/twijfelt -> unverified (fail-safe), nooit direct current
- [ ] #3 Niet-blokkerend bij SessionStart (detached) -- onzichtbaar/snel
- [ ] #4 Cross-memory: supersede/expire/cluster + hercontrole van current
- [ ] #5 render() hardening: _yaml_list string-guard + YAML-escape title/source_session
- [ ] #6 Deterministische plumbing unit-getest; LLM-call mockbaar
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Judge-backend besluit (advisor-bevestigd): LOKAAL Ollama-generatie-model achter een mockbare judge()-seam (spiegelt _embeddings.py provider-patroon). Headless `claude -p` AFGEWEZEN = cloud-leak (schendt randvoorwaarde #4). Geverifieerd 2026-06-27: /api/generate werkt lokaal; aanwezige generatie-modellen: qwen3.6:latest (24GB), gemma4:latest (9.6GB, ~35s cold), phi:latest (1.6GB, ~10s). Kies een capabel model (qwen3.6/gemma4) voor de judge, klein model voor snelle/CI-paden.

Sweep-uitvoering (advisor): SessionStart-hook = dunne launcher die de sweep DETACHED start (Popen zonder wait, stdout/stderr->logfile; Windows DETACHED_PROCESS|CREATE_NO_WINDOW, POSIX start_new_session=True), dan exit 0 fail-open. Verplicht: (1) single-flight lockfile (atomic create + PID/mtime + stale-reclaim) tegen overlappende sweeps; (2) heartbeat/status-file (last-run, counts, errors) -> SessionStart toont 1 regel + doctor checkt staleness (verzoent 'onzichtbaar' met 'luid bij falen'). Autonome capture-volledigheid hangt op auto_archive (geen archief -> alleen /sessielog vult).

/sessielog-pad mag later een verse in-sessie sub-agent als judge gebruiken (gebruiker zit al in Claude-sessie = cloud-consent), maar bouw nu EEN judge()-interface met lokale default; Claude-pad = toekomstige opt-in.
<!-- SECTION:NOTES:END -->
