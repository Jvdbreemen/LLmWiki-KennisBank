---
id: TASK-26.12
title: >-
  Optionele Headroom-compatibiliteit en vergelijking met KennisBank wrapper
  evalueren
status: Done
assignee: []
created_date: '2026-07-08 18:08'
updated_date: '2026-07-11 20:32'
labels:
  - copilot
  - headroom
  - research
  - optional
dependencies:
  - TASK-26.1
  - TASK-26.7
references:
  - 'https://github.com/headroomlabs-ai/headroom'
modified_files:
  - docs/copilot-headroom-evaluation.md
parent_task_id: TASK-26
priority: low
ordinal: 28120
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Onderzoek of KennisBank optioneel met Headroom kan samenwerken zonder Headroom verplicht te maken. Beantwoord of Headroom als externe launcher KennisBank MCP/hooks/instructions meekrijgt, of er een clean integration point is, welke wrapper/proxy keuzes bruikbaar zijn, en of een importadapter voor Headroom logs/config zinvol is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een korte technische evaluatie van Headroom-compatibiliteit met KennisBank wrapper/MCP/hooks.
- [x] #2 De evaluatie onderscheidt inspiratie, optionele interoperabiliteit en expliciet niet-overgenomen runtime dependencies.
- [x] #3 Als integratie nuttig is, is er een aparte follow-up taak met ACs; zo niet, is dat besluit onderbouwd.
- [x] #4 Er is minimaal gekeken naar Headroom provider/wrapper/install code voor Claude, Codex, OpenCode/Copilot waar aanwezig.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
docs/copilot-headroom-evaluation.md (191 regels). Three-way classificatie: (1) inspiratie — interfaces geleend, geen code/runtime-dep (RegisterStatus-idempotentiecontract, prefer-CLI-then-file, key-scoped RMW, injectable COPILOT_HOME, doctor PASS/WARN/FAIL/SKIP + 0/1/2); (2) optionele interoperabiliteit — Headroom-wrap en KennisBank Copilot-config kunnen coexisten (disjuncte namespaced locaties die Headroom niet verwijdert), mogelijk maar niet gebouwd, harde grens: KennisBank bezit KENNISBANK_*, raakt nooit HEADROOM_*/COPILOT_PROVIDER_*; (3) expliciet niet-overgenomen runtime-deps (proxy/compressie-kern, API-rerouting, signal-teardown, Rust/ONNX/PyTorch). Import-adapter = NEE, op schema-niveau onderbouwd (Headroom persisteert alleen token-economie-telemetrie savings_ledger.py + sql/, geen sessie-kennis). Toekomstige interop = aparte follow-up (geen nu aangemaakt). Reviewed-sources citeert de echte Headroom-files (mcp_registry/base.py+claude.py verbatim, cli/wrap.py, cli/doctor.py, providers/copilot/, sql/). Cross-refs naar ADR-0003 D4/D5/D6/D7. Bevestigt: geen Headroom-dependency; kennisbank-copilot wrapper blijft standalone.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 De conclusie staat in docs/ of als backlog final summary.
- [x] #2 Geen Headroom dependency wordt toegevoegd zonder expliciete vervolgtaak.
- [x] #3 KennisBank wrapper blijft zelfstandig bruikbaar.
<!-- DOD:END -->
