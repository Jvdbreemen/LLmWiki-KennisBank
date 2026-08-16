---
id: TASK-110
title: >-
  MCP step 8 [GATED]: pin bump to mcp&gt;=2, only once a client actually needs
  it
status: To Do
assignee: []
created_date: '2026-07-29 22:46'
updated_date: '2026-07-30 05:29'
labels: []
dependencies:
  - TASK-102
ordinal: 106700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GATED - do not execute yet. The definitive plan (docs/superpowers/plans/mcp-2026-07-28-migration.md section 1) moves the pin bump to the LAST step and gates it on a measurement rather than a schedule. Measured 2026-07-30: a modern-only server dies against the clients actually in use with "McpError: Method not found: initialize", because their first frame is initialize and they never probe server/discover. Every inspectable client is pre-2026-07-28 and reads none of the new fields. Migrating early can only lose; waiting cannot. GATE (AND, not OR): (1) a client is observed sending io.modelcontextprotocol/protocolVersion = 2026-07-28 - closable in ten lines by logging inbound _meta to stderr for a week; AND (2) mcp 2.0.1 has shipped, since 2.0.0 has zero post-GA patch releases, with steps 1-7 green. Only then: version-aware install_python_dep in setup.sh:276-286 comparing the installed version rather than find_spec presence, setup.sh:290-292 installing the SDK whenever kb-mcp.py is registered for any agent, requirements.txt to mcp>=2.0.1,<3, and the modern-era wire assertions. Correction to the earlier brief: mcp 2.0.0 does NOT have zero field time - there was a seven-week public pre-release train (a1 2026-06-11 to rc1 07-27); the real gap is zero post-GA patches.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 setup.sh compares installed version against the requirement spec, not just module presence
- [ ] #2 setup.sh installs the SDK whenever kb-mcp.py is registered for any agent
- [ ] #3 The step-2 harness passes the legacy initialize flow against the new pin (the dual-era proof)
- [ ] #4 install-agent-envs.py:822-850 embedded client validator still reports a successful MCP handshake under the new pin
- [ ] #5 pytest suite green
- [ ] #6 GATE PROVEN before any code change: a client observed sending protocolVersion 2026-07-28, AND mcp 2.0.1 released
- [ ] #7 requirements.txt uses mcp>=2.0.1,<3 and the dual-path import at kb-mcp.py is unchanged
<!-- AC:END -->
