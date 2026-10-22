---
id: TASK-258
title: Add OMP (oh-my-pi) as a setup.sh agent target
status: In Progress
assignee: []
created_date: '2026-10-21T21:21:00Z'
updated_date: '2026-10-21T21:45:00Z'
labels:
  - omp
  - agents
  - setup
dependencies: []
priority: high
ordinal: 193600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
OMP reads the shared ~/.agents/skills but gets no KennisBank MCP server or instructions from setup.sh. Add --agents omp: key-scoped registration of mcpServers.kennisbank in ~/.omp/agent/mcp.json (PI_CODING_AGENT_DIR honoured), KennisBank instructions as a managed always-apply rule at ~/.omp/agent/rules/kennisbank.md (not ~/.omp/agent/AGENTS.md, which would shadow every other user context file), shared and command skills in ~/.agents/skills, validation, a read-only doctor section, and docs. No lifecycle hooks, as for Copilot.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 setup.sh --agents omp (and all) installs and validates the OMP integration idempotently
- [x] #2 mcpServers.kennisbank in the OMP user mcp.json pins KENNISBANK_VAULT and kb-mcp.py, preserving other servers
- [x] #3 The managed rule ~/.omp/agent/rules/kennisbank.md is always-apply and names the active vault; no AGENTS.md is written
- [x] #4 Validation fails on a missing or wrong-vault OMP registration; doctor.sh reports OMP read-only
- [x] #5 Tests cover install, idempotence, preservation of foreign config and validation
- [x] #6 AGENTS.md, README, docs/AGENT-INSTALL.md, docs/agent-integrations.md and CHANGELOG document the omp target
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented in scripts/_omp.py (reuses _copilot primitives), install-agent-envs.py, setup.sh, doctor.sh, agent-status.py. Verified: tests/test_omp_config.py (7), neighbouring agent tests (17 Hermes failures are WinError 1314 symlink privilege, environment), docs/setup consistency tests (84), test_setup_deploy.py (29). setup.sh --yes --agents omp in a Git Bash sandbox installed skills, mcp.json and the rule; its MCP runtime handshake timed out, which the codex target shows identically on this machine (environment, not OMP). Real OMP session confirmed the always-apply rule names the vault and 11 kennisbank MCP tools load. Note: a first smoke run used the WSL bash by mistake and refreshed scripts/migrations in the empty WSL scaffold vault /home/robert/KennisBank (no content files).
<!-- SECTION:NOTES:END -->
