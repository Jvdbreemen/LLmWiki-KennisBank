---
id: TASK-222
title: Harden lifecycle, privacy, setup, and cross-client support
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - memory
  - maintenance
  - privacy
  - setup
  - multi-client
dependencies:
  - TASK-214
  - TASK-217
  - TASK-220
ordinal: 176100
---

## Description

Make source and experience projections operationally safe. Add maintenance for
stale, superseded, retracted, redacted, and orphaned records. Ensure raw source
retention and deletion policy is explicit. Keep source indexes and experience
stores rebuildable and auditable.

Update setup, doctor, rebuild commands, configuration documentation, C4
architecture documentation, and client-facing retrieval descriptions. Validate
Claude Code, Codex, OpenCode, and Copilot paths where each client supports the
feature. Maintain the configured local vault boundary and fail-open behaviour;
do not create a cloud fallback.

Add operational observability for rebuild progress, source-index freshness,
experience extraction failures, provenance gaps, redaction skips, and disabled
routes. Ensure migrations have backups or recoverable derived-state rebuilds.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Setup and upgrade deploy or discover every new script, schema, command, and configuration entry idempotently
- [ ] #2 Doctor validates source-index health, provenance coverage, experience-store health, rebuildability, and disabled-route safety
- [ ] #3 Full and incremental rebuilds have progress, stale/orphan reporting, and recoverable failure behaviour
- [ ] #4 Retraction, supersession, narrowing, redaction, and source deletion have documented and tested effects on derived records
- [ ] #5 The configured local vault path and no-cloud boundary are preserved for every client
- [ ] #6 Supported client surfaces are smoke-tested for explicit source recall and gated experience recall where applicable
- [ ] #7 C4, README, configuration, and command/MCP documentation describe the final architecture and labels shown to users
- [ ] #8 A release/upgrade note records migration impact, rollback/rebuild instructions, and known limitations
<!-- AC:END -->

