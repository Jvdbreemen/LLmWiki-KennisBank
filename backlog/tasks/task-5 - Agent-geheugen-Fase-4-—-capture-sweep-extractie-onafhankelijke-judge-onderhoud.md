---
id: TASK-5
title: >-
  Agent-geheugen Fase 4 — capture & sweep (extractie + onafhankelijke judge +
  onderhoud)
status: To Do
assignee: []
created_date: '2026-06-26 23:22'
updated_date: '2026-06-27 08:34'
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
MODEL-ROUTER (gebruikerseis): bouw _llm.py als generatie-tegenhanger van _embeddings.py VÓÓR de judge. Eén seam generate(prompt, system="", timeout)->str|None, fail-soft. Config-resolutie eerste-match: env (KB_LLM_PROVIDER/KB_LLM_MODEL/KB_LLM_ENDPOINT/KB_LLM_API_KEY_ENV) -> <vault>/.claude/kennisbank-llm.json -> default.
Providers: ollama (LOKAAL, DEFAULT; POST localhost:11434/api/generate), openrouter (CLOUD opt-in; OpenAI-compat /chat/completions, api_key_env=OPENROUTER_API_KEY), claude-cli (CLOUD opt-in; shellt 'claude -p', gebruikt CC-auth). Default model gemma4:latest (wijzigbaar; qwen3.6 beter/trager, phi snel/CI).
Helpers: provider(), model_id() (idem embed_id), is_local() (ollama/lokaal True) voor doctor/heartbeat. CLI: 'python3 _llm.py current' + 'test'.
VEILIGHEID #4: default lokaal; cloud vereist EXPLICIETE config-wijziging. doctor no-cloud-check meldt actieve provider en WAARSCHUWT luid als niet-lokaal (content verlaat machine). De no-cloud-test mag _llm.py's cloud-endpoints als string bevatten (ze zijn opt-in/gegate), maar moet asserteren dat de DEFAULT/actieve config lokaal is.
judge() = dunne laag op _llm.generate(); mockbare seam (tests monkeypatchen generate). Vervangt het eerdere 'alleen Ollama'-besluit: nu configureerbare router, lokaal-default.
<!-- SECTION:NOTES:END -->
