---
id: TASK-5.1
title: Agent-geheugen Fase 4a — model-router + seams + render-hardening
status: In Progress
assignee: []
created_date: '2026-06-27 09:36'
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
- [ ] #1 _llm.py provider-keten default [ollama], generate() probeert op volgorde, cloud-stap luid naar stderr
- [ ] #2 is_local() True alleen als eerste provider lokaal; env/file/default config-resolutie
- [ ] #3 render() gehard: embedded quotes/newlines gesanitized, _yaml_list accepteert string; geldige input ongewijzigd
- [ ] #4 _judge.judge() fail-safe: None/parse-fout/onbekend -> unverified; alleen expliciet current promoot
- [ ] #5 _extract.extract_candidates() fail-safe -> []; begrensd op max_n; lege bodies gefilterd
- [ ] #6 Alle tests mockbaar zonder echt model/netwerk
<!-- AC:END -->
