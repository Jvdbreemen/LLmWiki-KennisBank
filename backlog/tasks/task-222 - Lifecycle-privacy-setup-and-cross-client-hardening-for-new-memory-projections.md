---
id: TASK-222
title: Harden lifecycle, privacy, setup, and cross-client support
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-26 00:00'
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
- [x] #1 Setup and upgrade deploy or discover every new script, schema, command, and configuration entry idempotently
- [x] #2 Doctor validates source-index health, provenance coverage, experience-store health, rebuildability, and disabled-route safety
- [x] #3 Full and incremental rebuilds have progress, stale/orphan reporting, and recoverable failure behaviour
- [x] #4 Retraction, supersession, narrowing, redaction, and source deletion have documented and tested effects on derived records
- [x] #5 The configured local vault path and no-cloud boundary are preserved for every client
- [x] #6 Supported client surfaces are smoke-tested for explicit source recall and gated experience recall where applicable
- [x] #7 C4, README, configuration, and command/MCP documentation describe the final architecture and labels shown to users
- [x] #8 A release/upgrade note records migration impact, rollback/rebuild instructions, and known limitations
<!-- AC:END -->

## Evidence

- `setup.sh` already deploys all `scripts/*.py` and `commands/**/*.md`
  idempotently; settings migration preserves existing values and adds the two
  opt-in toggles. `tests/test_setup_deploy.py` verifies the rebuild, recall,
  proposal, evaluation, and projection-doctor surfaces. The combined agent/
  setup selection passed with 33 tests and 4 deselected in 305.82s.
- `kb-projection-doctor.py` is read-only and reports schema state, provenance
  coverage, stale/orphan source rows, experience lifecycle status, redaction
  signals, rebuildability, and disabled routes.
- `build-source-index.py` and `rebuild-experience.py` emit progress and use
  staging plus atomic replacement. Focused rebuild/health/source tests pass,
  including failure preservation; the maintenance/doctor selection is 6/6.
- Claude Code receives namespaced commands; Codex, OpenCode, and Copilot use
  the same configured vault and the MCP server now exposes read-only
  `source_recall` and `experience_recall`. The MCP/setup smoke contract passed
  after the tool-set update.
- Architecture, README, configuration, command, MCP, and upgrade notes now
  describe evidence labels, local-only boundaries, and the hold gate.

## Remaining evidence gap

The lifecycle fixture now covers narrowing alongside retraction, supersession,
redaction, and source-deletion diagnostics. Product value remains a separate
hold: the configured live vault has no reviewed
experience holdout, and the source smoke set is not a representative paired
downstream evaluation.
