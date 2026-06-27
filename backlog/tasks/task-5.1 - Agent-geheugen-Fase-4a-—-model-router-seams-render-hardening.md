---
id: TASK-5.1
title: Agent-geheugen Fase 4a — model-router + seams + render-hardening
status: Done
assignee: []
created_date: '2026-06-27 09:36'
updated_date: '2026-06-27 10:05'
labels:
  - agent-geheugen
milestone: Agent-geheugen
dependencies: []
references:
  - docs/superpowers/plans/2026-06-27-agent-geheugen-fase4a-router-seams.md
parent_task_id: TASK-5
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Testbare bouwstenen voor de sweep: _llm.py lokaal-first model-router (provider-keten default [ollama], opt-in cloud openrouter/claude-cli, luid bij cloud-stap, is_local), render() input-hardening in _memory.py (sanitize scalars + _yaml_list string-guard), _judge.py oordeel-seam (fail-safe naar unverified), _extract.py kandidaat-extractie-seam (fail-safe naar []). Alles puur, mockbaar (_llm.generate seam), unit-getest zonder echt model.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 _llm.py provider-keten default [ollama], generate() probeert op volgorde, cloud-stap luid naar stderr
- [x] #2 is_local() True alleen als eerste provider lokaal; env/file/default config-resolutie
- [x] #3 render() gehard: embedded quotes/newlines gesanitized, _yaml_list accepteert string; geldige input ongewijzigd
- [x] #4 _judge.judge() fail-safe: None/parse-fout/onbekend -> unverified; alleen expliciet current promoot
- [x] #5 _extract.extract_candidates() fail-safe -> []; begrensd op max_n; lege bodies gefilterd
- [x] #6 Alle tests mockbaar zonder echt model/netwerk
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fase 4a afgerond. _llm.py lokaal-first model-router (provider-keten default [ollama], opt-in cloud openrouter/claude-cli, luid+flush bij cloud-stap, is_local), render() input-hardening (_yaml_scalar sanitize + _yaml_list string-guard, geen regressie), _judge.py (fail-safe naar unverified), _extract.py (fail-safe naar []). Commits 7f9a4c5, 766ec32, 4b7b61e, e17748e + privacy-polish (flush+test). 174 tests groen. Multi-dimensie whole-branch review (20 agents): 0 Critical/Important/Minor confirmed — privacy/fail-safe/render dimensies PASS. Privacy-noot voor fase-5 doctor: is_local() classificeert op provider-NAAM niet endpoint (remote-ollama zou stil lekken; latent want niets gate't erop).
<!-- SECTION:FINAL_SUMMARY:END -->
