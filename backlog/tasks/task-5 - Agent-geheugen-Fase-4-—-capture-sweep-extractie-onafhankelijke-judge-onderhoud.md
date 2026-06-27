---
id: TASK-5
title: >-
  Agent-geheugen Fase 4 — capture & sweep (extractie + onafhankelijke judge +
  onderhoud)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 09:31'
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
FALLBACK-KETEN (gebruiker akkoord, optie A): _llm.py leest een GEORDENDE provider-keten, default ["ollama"] (lokaal-only). generate() probeert providers op volgorde tot er één een niet-None resultaat geeft. GEEN automatische cloud-fallback by default — lokaal faalt => fail-safe (judge geeft None => memory blijft unverified, volgende sweep beoordeelt opnieuw; zelf-herstellend, nul leak). Gebruiker zet cloud opt-in door "openrouter"/"claude-cli" aan de keten toe te voegen in kennisbank-llm.json (config = expliciete toestemming, #4). VERPLICHT luid loggen wanneer een cloud-stap vuurt: stderr + heartbeat-status + sessiestart-melding ("judge viel terug op <provider> — content naar cloud"). Nooit stil, ook niet als geconfigureerd. doctor no-cloud-check: meld de keten; waarschuw als die een cloud-provider bevat. Config-vorm bv: {"providers": ["ollama"], "models": {"ollama":"gemma4:latest","openrouter":"...","claude-cli":"-"}} of per-provider model. is_local() = True alleen als de ACTIEVE/eerste-geslaagde provider lokaal is.
<!-- SECTION:NOTES:END -->
