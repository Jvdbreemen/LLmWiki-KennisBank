---
id: TASK-26.1
title: >-
  Copilot CLI + Headroom research synthese en ADR voor lokale
  integratie-architectuur
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 19:45'
labels:
  - copilot
  - research
  - adr
  - headroom
dependencies: []
references:
  - docs/adr/0003-copilot-cli-integration.md
parent_task_id: TASK-26
priority: high
ordinal: 28010
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Onderzoek en leg vast hoe GitHub Copilot CLI lokaal integreert met instructies, MCP, hooks en custom agents, en hoe Headroom dit soort multi-agent integratie oplost via wrapper/proxy/config-mutatie.

Uitkomst moet een ADR/design spec zijn die beschrijft:
- welke Copilot CLI oppervlakken KennisBank gebruikt;
- welke config-bestanden veilig gemuteerd mogen worden;
- welke fallback geldt als Copilot niet geinstalleerd of niet ingelogd is;
- wat we overnemen van het Headroom-patroon: wrapper start lokale infrastructuur, zet env, registreert providerconfig, valideert en start daarna de echte agent;
- welke risico's er zijn rond account-auth, cloud policies, hooks en logging;
- hoe deze integratie past naast Claude Code, Codex, OpenCode en toekomstige agents.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een ADR of design document onder docs/ dat Copilot CLI integratieoppervlakken en Headroom-wrapperpatronen samenvat met bronlinks.
- [x] #2 De ADR kiest expliciet voor een local-first architectuur zonder Headroom runtime dependency en benoemt welke Headroom-ideeen wel worden toegepast.
- [x] #3 De ADR benoemt exacte Copilot config-locaties voor Windows en cross-platform paden, inclusief global en repo-local instructies.
- [x] #4 De ADR bevat een threat/operational risk paragraaf voor credentials, cloud requests, hook payloads, transcript logging en rollback.
- [x] #5 De ADR definieert de acceptatie-smoke voor de latere implementatie: copilot detectie, MCP zichtbaar, hook event gevangen, rawlog geschreven, recall query werkt.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
ADR docs/adr/0003-copilot-cli-integration.md geschreven en Accepted. Surface geverifieerd tegen de ECHTE CLI (copilot v1.0.70 win32-x64, direct geprobed) + de 5 GitHub-docs + Headroom-broncode (mcp_registry/base.py+claude.py verbatim gelezen).

Kernbeslissingen (elk met een sectie D1-D7 die child-taken referencen via de per-task mapping):
- D1 MCP: idempotente JSON-merge van mcpServers.kennisbank in ~/.copilot/mcp-config.json (schema geverifieerd), login-vrij; hergebruik validate_mcp_runtime.
- D2 Instructies: AGENTS.md managed-block (werkt al voor Copilot) + ~/.copilot/copilot-instructions.md + custom agent-profiel ~/.copilot/agents/kennisbank.agent.md (LET OP: .agent.md-extensie verplicht).
- D3 Hooks: native Copilot-hooks BESTAAN (v1.0.21+, gehard v1.0.70) via ~/.copilot/hooks/kennisbank.json; cross-platform bash/powershell-keys matchen KennisBank's py-3/python3-conventie; ALTIJD exit 0 (fail-open; exit 2 = deny, timeout = fail-open).
- D4 Wrapper: triviale exec (env + os.execvp), GEEN Headroom-proxy/rerouting.
- D5 Rawlog: hooks (live events) + --share/session-state import (sessies), provenance agent=github-copilot-cli.
- D6 Config-mutatie: structured=key-scoped read-modify-write; freeform=marker-block (_replace_block).
- D7 Headroom-interop: GEEN import-adapter (Headroom persisteert alleen token-economie-telemetrie); inspiratie, geen runtime-dependency.

Config-locaties (Windows+POSIX) getabelleerd; COPILOT_HOME = hermetische testsleutel. Threat/risk-sectie (credentials/cloud opt-in, hook-payloads, transcript-logging, plaintext-MCP, rollback, version-drift). Acceptance-smoke (detectie→MCP→hook→rawlog→recall) gedefinieerd. nvm4w install-caveat gedocumenteerd (optional platform-binary komt niet mee).
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Document is gereviewd tegen de huidige GitHub Copilot CLI docs en Headroom repo-code.
- [x] #2 Geen implementatiebeslissing blijft vaag: elke latere child-taak kan naar een concrete ADR-sectie verwijzen.
- [x] #3 Tests/doctor implicaties zijn expliciet benoemd.
<!-- DOD:END -->
