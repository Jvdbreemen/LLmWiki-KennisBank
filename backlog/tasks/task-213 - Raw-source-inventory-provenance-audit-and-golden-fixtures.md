---
id: TASK-213
title: Raw-source inventory, provenance audit, and golden fixtures
status: To Do
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-25 00:00'
labels:
  - source-recall
  - provenance
  - evaluation
dependencies:
  - TASK-212
ordinal: 175200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measure whether the raw corpus can support reliable source recall before
building a new index. Inventory `01-raw`, `08-archive`, `05-bronnen`, imported
documents, transcripts, and any existing source links. Record which files have
stable paths, hashes, session ids, timestamps, client/role metadata, and
recoverable passage boundaries.

Create a small, versioned golden set covering:

- exact source lookup;
- long-tail facts that were lost from current memory;
- failed approaches and dead ends;
- superseded and narrowed claims;
- multi-session reconstruction;
- source conflicts and missing sources;
- Dutch/English and transcript formatting variation;
- sensitive/redacted content that must not leave the local boundary.

Include negative cases where the correct answer is "not found" or "unknown".
The set must contain expected source ids and acceptable surrounding windows, not
only expected answer text.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A machine-readable inventory reports source counts, types, missing metadata, duplicate hashes, and unreadable files
- [ ] #2 Every golden fixture has an expected source id or an explicit not-found/unknown verdict
- [ ] #3 The fixture set includes at least one supersession/narrowing case where the historical source must remain recoverable
- [ ] #4 Privacy and redaction rules are tested against representative raw content before indexing
- [ ] #5 Baseline source recall is measured without a new index, including the current groundcheck path where applicable
- [ ] #6 The report states the oracle ceiling: which questions cannot be answered because the evidence is absent or unrecoverable
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Do not use the entire vault as an unreviewed fixture set. Keep the golden set
small enough for repeatable local evaluation and record fixture provenance.
<!-- SECTION:NOTES:END -->

