---
id: TASK-26
title: 'EPIC: Lokale GitHub Copilot CLI-integratie voor KennisBank'
status: Done
assignee: []
created_date: '2026-07-08 05:47'
updated_date: '2026-07-11 21:51'
labels:
  - epic
  - copilot
  - local-agent
  - mcp
  - hooks
  - setup
dependencies: []
references:
  - 'https://github.com/headroomlabs-ai/headroom'
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks
  - >-
    https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
priority: high
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Epic: volledige lokale GitHub Copilot CLI-integratie voor KennisBank.

Doel: maak GitHub Copilot CLI een first-class lokale agent-omgeving naast Claude Code, Codex, OpenCode en andere agents. Een gebruiker moet via setup/upgrade kunnen kiezen voor Copilot-integratie, waarna Copilot lokaal dezelfde KennisBank-context, MCP-tools, hooks, temporal recall en rawlog-capture kan gebruiken als de andere ondersteunde agents.

Context uit onderzoek:
- GitHub Copilot CLI ondersteunt lokale custom instructions via AGENTS.md, .github/copilot-instructions.md, .github/instructions/*.instructions.md, $HOME/.copilot/copilot-instructions.md en COPILOT_CUSTOM_INSTRUCTIONS_DIRS.
- GitHub Copilot CLI ondersteunt MCP-servers via interactieve /mcp add of het copilot mcp add subcommand.
- GitHub Copilot CLI ondersteunt hooks voor agent lifecycle, toolgebruik, logging, policy checks en automatisering.
- GitHub Copilot CLI ondersteunt custom agents via .github/agents/ en ~/.copilot/agents/.
- Headroom laat een sterk patroon zien: een wrapper start lokale infrastructuur, configureert agent-specifieke env/config, registreert MCP/hooks/instructions idempotent en biedt unwrap/doctor.

Scope:
- Ontwerp en implementeer een local-first Copilot install target in setup.sh en upgradepad.
- Voeg een KennisBank Copilot wrapper/launcher toe die lokale env, MCP, hooks, instructions en logging vooraf valideert en daarna copilot start.
- Registreer de bestaande KennisBank MCP server bij Copilot CLI.
- Installeer Copilot-specifieke instructies, custom agent-profiel en hook-configuratie zonder bestaande gebruikersconfig te overschrijven.
- Capture/importeer Copilot CLI sessies of hook-events als raw logs en activity events met duidelijke provenance.
- Breid doctor/setup-validatie en docs uit zodat installatie aantoonbaar werkt.

Niet-doelen:
- Geen verplichte cloud memory dependency introduceren.
- Geen Headroom runtime dependency maken; Headroom is inspiratie voor wrapper/hook-architectuur, tenzij een latere taak expliciet een optionele integratie toevoegt.
- Geen GitHub Copilot abonnement of login automatisch forceren; detecteer en rapporteer status, maar laat account-authenticatie bij de gebruiker.
- Geen destructieve wijzigingen in ~/.copilot, repo .github of globale config zonder backup, markers en idempotente rollback.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh biedt GitHub Copilot CLI als expliciete agent-omgeving bij install en upgrade, met veilige defaults en geen overschrijving van bestaande config.
- [x] #2 KennisBank MCP-tools zijn lokaal beschikbaar in Copilot CLI en doctor kan dat aantonen zonder handmatige inspectie.
- [x] #3 Copilot hooks en/of wrapper leggen sessie- en toolactiviteit vast als rawlog/activity-events met source provenance en fail-open gedrag.
- [x] #4 Copilot leest KennisBank-specifieke instructies via AGENTS.md/copilot-instructions/local instruction dirs zonder conflicten met Claude/Codex/OpenCode.
- [x] #5 Er is een end-to-end validatiepad op Windows PowerShell dat copilot-detectie, MCP-config, hooks, wrapper, rawlog capture en recall-smoke test verifieert.
- [x] #6 README, CONFIGURATION, POST-INSTALL, AGENTS.md en changelog beschrijven de lokale Copilot-integratie en upgrade-impact.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
EPIC compleet: GitHub Copilot CLI (@github/copilot) is een first-class lokale agent naast Claude/Codex/OpenCode. Alle 13 child-taken Done (26.1-26.13).

Geleverd: ADR-0003 + Headroom-evaluatie; _copilot.py config-laag (idempotente MCP/hooks/instructions/agent-profiel, COPILOT_HOME-hermetisch, backups); kb-copilot-capture.py (fail-open, secret-redactie); import-copilot.py (rawlog→01-raw/transcripts→activity-index, recall via /watdeedik); kennisbank-copilot.py wrapper (triviale exec, --kb-doctor/-dry-run/-print-env/--no-capture, geen proxy); agent-status.py multi-agent samenvatting; setup.sh --agents copilot + install-agent-envs install_copilot + doctor.sh copilot-sectie; docs (README/CONFIGURATION/POST-INSTALL/AGENTS/TROUBLESHOOTING/CHANGELOG/agent-integrations).

Geverifieerd tegen de ECHTE copilot v1.0.70: config door CLI geconsumeerd (mcp list toont kennisbank), mcp-add-schema, hooks/agents-surfaces. Echte install op Windows-vault Kluis: alle Copilot-doctor-checks PASS (DoD#2). 8 hermetische testbestanden (fake copilot-binary fixture, opt-in live smoke); Claude/Codex/OpenCode-paden niet-regressief. Eén regressie (hardcoded vault-default in _copilot.py/kennisbank-copilot.py) door de volledige suite gevonden en gefixt (nu via vault_root()). Resterende full-suite-fouten = omgeving (sqlite_vec-extensie, load-timeout), niet van deze branch.

Commit cb10ba0 op feat/copilot-cli-integration; PR #27 naar Jvdbreemen upstream (OPEN, MERGEABLE, 40 files +4766).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Alle child-taken zijn Done of expliciet Blocked met reden en eigenaar.
- [x] #2 setup + doctor slagen op een lokale Windows-installatie met vaultpad D:\Users\Robert\Documents\Claude\Projects\Kluis.
- [x] #3 Er is testdekking voor config-mutatie, idempotentie, hook payload parsing, MCP registratie en wrapper launch-env.
- [x] #4 Een release note vermeldt Copilot CLI als ondersteunde lokale agent-omgeving.
<!-- DOD:END -->
