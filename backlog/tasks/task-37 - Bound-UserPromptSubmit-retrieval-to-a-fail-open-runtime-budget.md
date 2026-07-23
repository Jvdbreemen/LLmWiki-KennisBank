---
id: TASK-37
title: Bound UserPromptSubmit retrieval to a fail-open runtime budget
status: Done
assignee: []
created_date: '2026-07-23 21:30'
updated_date: '2026-07-23 22:13'
labels:
  - hooks
  - retrieval
  - reliability
  - windows
dependencies: []
modified_files:
  - scripts/kb-retrieve.py
  - tests/test_kb_retrieve_wiki.py
  - kennisbank-embed.example.json
  - CONFIGURATION.md
priority: high
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The live Claude UserPromptSubmit hook can spend about 30 seconds waiting for a cold or unavailable Ollama embedding while its client hook timeout is 25-30 seconds. The host then kills the process before Python's fail-open exception path can return exit 0. Bound the interactive embedding call well below the client ceiling, preserve valid single-object JSON output, and add deterministic regression coverage. Deploy only through the supported setup path to the configured Kluis vault.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Cold or unavailable embeddings return no context and exit 0 within a small bounded runtime.
- [x] #2 A configured retrieval timeout cannot accidentally consume the full Claude hook timeout without explicit opt-in.
- [x] #3 Successful retrieval still embeds the prompt once and preserves wiki plus memory recall behavior.
- [x] #4 The emitted UserPromptSubmit payload is exactly one valid JSON object and carries suppressOutput.
- [x] #5 Focused retrieval, hook registration, and deploy tests pass.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause reproduced on the live Kluis hook: a cold/unavailable Ollama embed waited up to 20 seconds and the failed wiki embed was retried by memory recall, allowing the client to kill the process before fail-open. The prompt embed is now capped at 2 seconds by default, requires a separate explicit ceiling opt-in to run longer, and records whether an attempt occurred so wiki and memory share exactly one embed attempt. Deployed through setup.sh to the configured Kluis vault. Focused verification: 31 passed, 1 skipped; three relevant setup/deploy tests passed; unavailable and live endpoints both exited 0 in about 3.2 seconds with empty-or-valid JSON. Full doctor reached 113 PASS and failed only on three pre-existing wiki provenance records, outside this task.

PR #49 review follow-up: isolate KB_RETRIEVE_TIMEOUT and KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT in timeout-budget tests so developer/CI environment variables cannot change their assertions.

PR #49 review follow-up verified under hostile inherited timeout values (KB_RETRIEVE_TIMEOUT=17 and KB_PROMPT_HOOK_MAX_EMBED_TIMEOUT=19): 31 passed, 1 skipped. Timeout-budget tests now clear the inherited environment and opt in only to values under test.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Bound UserPromptSubmit retrieval to one fail-open embed attempt with a 2-second default ceiling, documented the opt-in override, added regression coverage, and deployed the exact tested script to Kluis.

Made prompt timeout tests hermetic by centralizing a cleared prompt-hook environment, covering both timeout computation and wiki embedding calls.
<!-- SECTION:FINAL_SUMMARY:END -->
