---
id: TASK-26.13
title: 'Dashboard: setup install-scherm en post-install multi-agent statussamenvatting'
status: Done
assignee: []
created_date: '2026-07-11 19:23'
updated_date: '2026-07-11 20:40'
labels:
  - copilot
  - setup
  - dashboard
  - ux
dependencies:
  - TASK-26.3
  - TASK-26.9
modified_files:
  - setup.sh
  - scripts/agent-status.py
  - tests/test_agent_status.py
parent_task_id: TASK-26
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De 'dashboard' die de gebruiker voor zich ziet: het setup/upgrade agent-keuzescherm plus een heldere health-samenvatting na afloop. Terminal-only, past bij de noord-ster (onzichtbaar, snel, uit de weg) — geen web-UI, geen levende service.

Twee onderdelen:
1. Agent-keuzescherm bij install en upgrade toont alle ondersteunde agents (Claude, Codex, OpenCode, GitHub Copilot CLI) met detectiestatus (gevonden / niet gevonden / al geconfigureerd), zodat de gebruiker bewust kiest.
2. Na install/upgrade een compacte samenvatting per agent: MCP geregistreerd?, hooks actief?, laatste rawlog?, recall-smoke ok? — met PASS/WARN/FAIL-telling. Copilot toont 'overgeslagen (installeer @github/copilot)' wanneer afwezig, non-fatal.

Bouwt voort op 26.3 (setup agent-keuze) en 26.9 (doctor checks); hergebruikt bestaande doctor-infra i.p.v. een nieuw runtime-oppervlak.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Setup/upgrade toont een agent-keuzescherm met per agent een detectiestatus (found/not-found/already-configured) in zowel interactieve als non-interactive mode
- [x] #2 Na install/upgrade verschijnt een per-agent statussamenvatting (MCP, hooks, rawlog, recall) met PASS/WARN/FAIL-telling
- [x] #3 Copilot verschijnt als optie ook wanneer niet geinstalleerd, gemarkeerd non-fatal met concreet installatie-advies
- [x] #4 De samenvatting hergebruikt bestaande doctor/install-agent-envs output (JSON) en introduceert geen nieuw runtime-oppervlak
- [x] #5 Tests dekken de detectiestatus-rendering en de samenvatting voor aanwezige en afwezige agents
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Twee delen. (1) Install-scherm: setup.sh agent-keuzescherm toont per agent een detectiestatus (claude/codex/opencode + copilot met _copilot.py detect → gevonden vX / niet gevonden / binary onvolledig) in interactieve mode; --agents flag voor non-interactive. (2) Post-install samenvatting: scripts/agent-status.py rendert een compacte per-agent rollup (configured?, MCP registered?, voor copilot installed+versie) + summary-telling, hergebruikt bestaande on-disk config + _copilot.detect (geen nieuw runtime-oppervlak, AC#4). Copilot toont non-fatal 'skipped - not installed (npm install -g @github/copilot)' of '!! installed vX, not registered'. In setup.sh na de doctor-gate, fail-soft. ASCII-marks (cp1252/Windows-veilig, ADR-0002). JSON-mode voor machineconsumptie. Live geverifieerd op deze machine: [ok] claude/codex/opencode, [!!] copilot v1.0.70 not registered. 6 tests (copilot skipped/configured, codex/opencode/claude detectie, rollup+render, JSON-CLI).
<!-- SECTION:FINAL_SUMMARY:END -->
