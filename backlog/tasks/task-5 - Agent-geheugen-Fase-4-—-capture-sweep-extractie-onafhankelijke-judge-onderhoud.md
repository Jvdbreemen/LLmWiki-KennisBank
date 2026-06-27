---
id: TASK-5
title: >-
  Agent-geheugen Fase 4 — capture & sweep (extractie + onafhankelijke judge +
  onderhoud)
status: Done
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 11:24'
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
- [x] #1 Sweep extraheert+judget nieuwe transcripts, verse-context (onafhankelijk van producent)
- [x] #2 Judge faalt/twijfelt -> unverified (fail-safe), nooit direct current
- [x] #3 Niet-blokkerend bij SessionStart (detached) -- onzichtbaar/snel
- [ ] #4 Cross-memory: supersede/expire/cluster + hercontrole van current
- [x] #5 render() hardening: _yaml_list string-guard + YAML-escape title/source_session
- [x] #6 Deterministische plumbing unit-getest; LLM-call mockbaar
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
FASE-4b REQUIREMENTS (uit fase-4a review integratie-dimensie):
1. CHUNK lange transcripts vóór _extract (BELANGRIJK): extract propt nu het hele transcript in één prompt -> lange sessies vallen stil naar [] (model-context-overflow). 4b moet transcripts splitsen in chunks en per chunk extracten + samenvoegen.
2. DEDUP-primitief: 4b heeft een dedup nodig (cosine van kandidaat-embedding vs bestaande memory; hergebruik _embeddings + semantic-tiling-patroon, DEDUP_THRESHOLD ~0.92 empirisch).
3. WRITE-COLLISION-GUARD: _memory.write gebruikt datum-slug; twee kandidaten zelfde dag/slug botsen -> 4b moet uniek pad garanderen (suffix/teller).
4. SWEEP-BREED TIMEOUT-BUDGET + CANCEL: _llm.generate heeft alleen per-provider timeout (120s, hangt niet oneindig want stream=False). 4b detached sweep heeft een aggregaat-budget + stop-conditie nodig (niet eindeloos doorploegen).
5. WATERMARK: spiegel distill-notify .distilled-pattern met een .swept-watermark in 01-raw/transcripts/ (pending()/mark()) voor 'nieuw sinds vorige sweep'.
6. ORKESTRATIE zet zelf status (uit judge-verdict), evidence_basis="agent", source_session (transcript-pad) -> _memory.write accepteert die al, geen seam-gat.

FASE-5 DOCTOR-NOOT: is_local() is provider-NAAM-gebaseerd; doctor no-cloud-check moet ook het ACTIEVE ollama-endpoint checken (waarschuw als niet localhost/127.0.0.1 -> remote-ollama lekt stil).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase 4 (capture & sweep) afgerond via 4a (model-router + seams + render-hardening, TASK-5.1) + 4b (sweep-orkestratie, TASK-5.2). Autonome capture: SessionStart-launcher (detached, lockfile, gegate op memory_capture) -> sweep leest nieuwe transcripts (.swept-watermark) -> chunk -> extract -> dedup -> onafhankelijke judge (fail-safe naar unverified) -> schrijf met status/evidence_basis=agent/source_session -> mark; expire-pass + heartbeat; build-kb-index erna. Model-router _llm.py lokaal-first (opt-in cloud-keten, luid). Upfront chat+embed-probe voorkomt watermark-burn bij outage. ~204 tests groen; twee whole-branch reviews (20+24 agents) + fix-waves. AC#4 cross-memory: expire gedaan; supersede/cluster/hercontrole -> TASK-8 (v2, in ontwerp). AC#5 render-hardening in 4a.
<!-- SECTION:FINAL_SUMMARY:END -->
