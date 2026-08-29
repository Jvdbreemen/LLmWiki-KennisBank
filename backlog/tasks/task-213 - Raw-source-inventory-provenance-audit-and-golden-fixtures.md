---
id: TASK-213
title: Raw-source inventory, provenance audit, and golden fixtures
status: Done
assignee: []
created_date: '2026-08-25 00:00'
updated_date: '2026-08-29 00:00'
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
- [x] #1 A machine-readable inventory reports source counts, types, missing metadata, duplicate hashes, and unreadable files
- [x] #2 Every golden fixture has an expected source id or an explicit not-found/unknown verdict
- [x] #3 The fixture set includes at least one supersession/narrowing case where the historical source must remain recoverable
- [x] #4 Privacy and redaction rules are tested against representative raw content before indexing
- [x] #5 Baseline source recall is measured without a new index, including the current groundcheck path where applicable
- [x] #6 The report states the oracle ceiling: which questions cannot be answered because the evidence is absent or unrecoverable
<!-- AC:END -->

## Implementation Notes
<!-- SECTION:NOTES:BEGIN -->
Do not use the entire vault as an unreviewed fixture set. Keep the golden set
small enough for repeatable local evaluation and record fixture provenance.

### Progress evidence

- `docs/research/raw-source-inventory-2026-08-26.md` records a read-only scan
  of 16,255 approved text files: 0 unreadable and 2,784 duplicate hash groups.
- `tests/test_raw_source_inventory.py` and
  `tests/test_build_source_index.py` cover redaction counting, redaction
  exclusion/reporting, and safe rebuild behaviour.
- `scripts/_source_holdout.py` and `scripts/build-source-holdout.py` now
  validate approved paths, hashes, offsets, explicit negative verdicts, and
  sensitive cases; the frozen manifest strips raw passages and answers.
- `scripts/source-holdout-report.py` and `commands/kennisbank/source-holdout-report.md`
  provide a read-only aggregate oracle-ceiling report. Changed, missing, or
  unreadable sources are separated from intentional `not_found`/`unknown`
  cases, without printing reviewed content.
- Focused evidence: `22 passed` for the source, holdout, inventory, and
  evaluation-runner contracts; `31 passed` for the complete TASK-213 focused
  regression selection including both holdout CLIs.

The private reviewed holdout now contains 50 positive, 9 `unknown`, and 1
`not_found` case over 28 expected documents. All positive hashes and windows
resolve (oracle ceiling 1.00). The historical-release case preserves retrieval
of the older source while testing a changed latest-marker interpretation.

The no-vector full-corpus FTS baseline indexed 16,271 approved documents
(781,127,644 bytes) in 247.455 seconds. It measured hit@5 0.66, MRR 0.531,
and no-hit precision 0.00. This completes the baseline measurement while
providing negative evidence against treating a naive full-vector build as the
automatic next step. Aggregate evidence is in
`docs/research/source-experience-evidence-packet-2026-08-29.md`; private cases
remain outside the repository boundary.
<!-- SECTION:NOTES:END -->
