---
id: TASK-155
title: A NOOP throws a memory away and leaves no record of what it was
status: In Progress
assignee: []
created_date: '2026-08-13 18:34'
updated_date: '2026-08-13 19:23'
labels:
  - memory
  - observability
dependencies: []
priority: medium
ordinal: 149700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Of the three reconcile actions, NOOP is the only one where the candidate memory is not written. The heartbeat counts `reconcile_noop`, so we know how often it happened; nothing anywhere says WHAT was discarded.

That is the same shape as TASK-150 one step earlier in the pipeline. There, a superseded memory existed on disk but appeared in no path a human uses, which is functionally deletion. Here the memory never reaches disk at all, so there is not even a file to reopen.

It matters because NOOP is exactly the action models get wrong. Measured on 20 unrelated pairs with the old prompt, qwen3.5:4b answered NOOP 25% of the time with reasons that said, in so many words, "these are unrelated" — the definition of ADD (TASK-144). The prompt fix took that to 0%, but the mechanism that made the loss invisible is untouched: a future prompt, model or threshold change can reintroduce it and nothing will say so.

Record every discarded candidate the way closures are recorded: title, body, which existing memory covered it, the judge's reason, and the prompt version. `.claude/memory-noop-log.jsonl`, beside `memory-closed-log.jsonl`, with a `memory-doctor.py discarded` view over it. Same rules as the closed log: a record, never a gate — if the log cannot be written, the sweep carries on.

Then the question "is the reconcile seam throwing away good knowledge?" becomes answerable by reading, instead of by re-running a measurement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every NOOP writes a record with the candidate title and body, the covering memory, the judge's reason and the prompt version
- [x] #2 memory-doctor.py shows recent discards, with --json for the heartbeat
- [x] #3 A broken log never blocks the sweep, proven by a test
- [x] #4 The log is bounded so a long --all rebuild cannot fill the disk
- [ ] #5 python -m pytest tests -q is green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Implementation, 2026-08-13

`.claude/memory-noop-log.jsonl` beside the closure log, with the same rules:
append-only, fail-soft, never a gate. `memory-doctor.py discarded [--json]
[--limit N]` reads it back.

`reconcile()` now reports `covered_by` on every return, not just on NOOP. A
record that says a candidate was discarded without saying by WHAT cannot be
judged, and putting the field on every branch means callers need no special
case. The wire contract grows a key rather than changing one, so nothing
breaks.

Two things this log does that the closure log does not have to:

- **It is bounded.** Closures are rare; NOOPs are not. Every re-capture of
  covered knowledge is one, and an `--all` rebuild over hundreds of transcripts
  could produce thousands. Trimmed to 2000 lines, oldest first, and only when
  the file is meaningfully over the limit so a long rebuild does not rewrite it
  on every line.
- **It offers no way back.** `closed` has `reopen`; a discarded candidate never
  became a file, so there is nothing to reopen. The CLI says so explicitly
  rather than leaving the reader to wonder.

The stored record carries title, body, the covering memory's stem, the reason
and the reconcile prompt version — so a future regression is attributable to a
prompt rather than merely visible.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Every NOOP now writes what it discarded to `.claude/memory-noop-log.jsonl`, readable through `memory-doctor.py discarded`. The question "is the reconcile seam throwing away good knowledge?" is answerable by reading instead of by re-running a measurement.

`reconcile()` reports `covered_by` on every return so the record names the memory that displaced the candidate. The log is bounded at 2000 lines because NOOPs, unlike closures, are common, and it offers no reopen: a discarded candidate never became a file, and the CLI says so rather than implying otherwise.
<!-- SECTION:FINAL_SUMMARY:END -->
