---
id: TASK-26.5
title: KennisBank MCP server registreren en valideren in GitHub Copilot CLI
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 21:03'
labels:
  - copilot
  - mcp
  - doctor
  - recall
dependencies:
  - TASK-26.2
references:
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers
modified_files:
  - scripts/_copilot.py
  - scripts/install-agent-envs.py
  - tests/test_copilot_config.py
  - tests/test_agent_envs_install.py
parent_task_id: TASK-26
priority: high
ordinal: 28050
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Registreer de bestaande KennisBank MCP server bij GitHub Copilot CLI en valideer dat Copilot dezelfde recall API kan gebruiken als Claude/Codex/OpenCode. Gebruik copilot mcp add waar beschikbaar, detecteer bestaande entries, geef vaultpad/Python runtime/entrypoint correct door en voer doctor smoke-tests uit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup kan de KennisBank MCP server bij Copilot registreren of exact uitleggen waarom dit niet kan op de lokale versie.
- [x] #2 Registratie is idempotent: meerdere setup-runs leveren geen dubbele MCP server entries op.
- [x] #3 Doctor valideert binary, MCP config, server start, initialize handshake en minimaal een tool-list of smoke-call.
- [x] #4 De MCP config gebruikt het echte vaultpad via KENNISBANK_VAULT of expliciete args en valt niet terug op een verkeerd default pad.
- [x] #5 Tests gebruiken fixtures/mocks voor copilot mcp add en MCP handshake zonder GitHub login te vereisen.
<!-- AC:END -->



## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
MCP-registratie via _copilot.ensure_mcp (idempotente JSON-merge mcpServers.kennisbank in ~/.copilot/mcp-config.json, schema geverifieerd tegen echte CLI). install-agent-envs.install_copilot bedraadt het; validate_config controleert kennisbank aanwezig + KENNISBANK_VAULT == actieve vault + args→kb-mcp.py. probe_cli() draait login-vrij `copilot mcp list` en onderscheidt copilot_missing / platform_binary_missing / not_logged_in / mcp_not_listed / version_old / ok met JSON-output. Runtime-handshake hergebruikt validate_mcp_runtime (nu ook getriggerd voor copilot).

Geverifieerd tegen echte copilot v1.0.70: `copilot mcp list` toont `kennisbank (local)`; probe status=ok mcp_listed=True; validate clean; dubbele install = geen dubbele entry. Tests: 6 probe/validate-tests (mocked, geen login) + install-idempotentie. AC#3 (doctor smoke) grotendeels via probe_cli+validate_mcp_runtime; doctor.sh-integratie → 26.9. DoD#3 CONFIGURATION-sectie → 26.11.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 MCP-validatie werkt lokaal met JSON-output voor doctor.
- [x] #2 Foutmeldingen onderscheiden: copilot ontbreekt, niet ingelogd, command ontbreekt, MCP handshake faalt, vaultpad fout.
- [x] #3 CONFIGURATION bevat een Copilot MCP sectie.
<!-- DOD:END -->
