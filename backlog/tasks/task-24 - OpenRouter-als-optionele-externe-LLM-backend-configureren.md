---
id: TASK-24
title: OpenRouter als optionele externe LLM-backend configureren
status: Done
assignee: []
created_date: '2026-07-07 19:23'
updated_date: '2026-07-07 20:40'
labels:
  - config llm openrouter setup
dependencies: []
modified_files:
  - setup.sh
  - scripts/install-agent-envs.py
  - scripts/_llm.py
  - scripts/register-hooks.py
  - kennisbank-llm.example.json
  - README.md
  - CHANGELOG.md
  - CONFIGURATION.md
  - AGENTS.md
  - docs/agent-integrations.md
  - tests/test_agent_envs_install.py
  - tests/test_llm.py
  - tests/test_register_hooks.py
  - tests/test_setup_deploy.py
priority: medium
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Maak KennisBank configureerbaar zodat gebruikers naast lokale Ollama-modellen ook bewust een externe OpenRouter API kunnen gebruiken voor LLM judge/extractie. De default blijft local-only/Ollama; OpenRouter is expliciet opt-in met duidelijke privacygrens en API-key env-var.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh kan de LLM-backend configureren of repareren voor Ollama default en OpenRouter opt-in zonder secrets in repo of vault te schrijven.
- [x] #2 kennisbank-llm.json ondersteunt OpenRouter met model, endpoint en api_key_env; _llm.py valideert config en faalt luid/fail-soft bij ontbrekende key.
- [x] #3 Post-install validatie test de gekozen backend: Ollama lokaal via smoke-test, OpenRouter via een minimale API smoke of duidelijke skip wanneer key ontbreekt.
- [x] #4 README.md, CONFIGURATION.md en AGENTS.md documenteren OpenRouter als bewuste cloud-optie inclusief data/privacy waarschuwing.
- [x] #5 Regressietests dekken config-resolutie, setup-validatie en dat Ollama local-only default blijft.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Ollama blijft de default LLM-backend in setup. Interactive setup biedt OpenRouter als expliciete opt-in met model slug en API-key env-var; optioneel ingevoerde keys worden alleen user-local opgeslagen buiten repo en vault. Agentinstall/validatie dekt Claude, Codex en OpenCode, inclusief backend smoke-tests. Validatie: 41 unittest setup/LLM/agent tests OK, echte setup tegen D:/Users/Robert/Documents/Claude/Projects/Kluis exit 0 met validation PASS en doctor 91 PASS / 1 WARN / 0 FAIL.

Releasevoorbereiding toegevoegd: README productintro bijgewerkt voor v0.12.0, CHANGELOG.md release-entry en compare-links bijgewerkt.

Hotfix toegevoegd na lokale Codex-verificatie: dubbele [mcp_servers.kennisbank.env] in ~/.codex/config.toml gerepareerd, TOML-validatie toegevoegd, codex mcp list gevalideerd.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests toegevoegd of aangepast voor OpenRouter-config.
- [x] #2 Documentatie bijgewerkt.
- [x] #3 Geen API keys of secrets in bestanden.
<!-- DOD:END -->
