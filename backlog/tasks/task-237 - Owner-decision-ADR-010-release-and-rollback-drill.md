---
id: TASK-237
title: Complete owner decision, ADR-010 lifecycle, release, and rollback drill
status: To Do
assignee: []
created_date: '2026-09-04 00:00'
labels:
  - release
  - adr
  - rollback
  - owner-gate
dependencies:
  - TASK-236
ordinal: 177600
---

## Description

Present the complete production evidence and unresolved risks to the owner.
Only an explicit accept/amend decision may change ADR-010 and authorize merge
and release. Exercise flag-only rollback before release and retain all canonical
ledger/source evidence.

## Acceptance Criteria

- [ ] #1 Evidence review lists every passed and failed gate without averaging failures away
- [ ] #2 Owner explicitly chooses accept, amend, or reject for ADR-010
- [ ] #3 ADR status history is appended through the repository's ADR lifecycle tooling; historical content is preserved
- [ ] #4 Flag-only rollback is exercised and restores ordinary recall without ledger deletion
- [ ] #5 Release checklist validates changelog, version, migration note, setup/upgrade, all clients, full tests, branch diff, and rollback instructions
- [ ] #6 Merge/release occurs only after owner approval; a failed gate produces a documented hold or rejection instead
- [ ] #7 Post-release doctor and explicit source/experience smoke pass on the deployed local vault

## Evidence

Record the owner decision, ADR transition, rollback drill, release commit/tag,
and post-release checks. Do not place private canary content in this file.
